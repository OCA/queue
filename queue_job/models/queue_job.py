# Copyright 2013-2016 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging
from datetime import datetime, timedelta

from odoo import models, fields, api, exceptions, _
# Import `Serialized` field straight to avoid:
# * remember to use --load=base_sparse_field...
# * make pytest happy
# * make everybody happy :
from odoo.addons.base_sparse_field.models.fields import Serialized

from ..job import STATES, DONE, PENDING, Job
from ..fields import JobSerialized

_logger = logging.getLogger(__name__)


def channel_func_name(model, method):
    return '<%s>.%s' % (model._name, method.__name__)


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""
    _name = 'queue.job'
    _description = 'Queue Job'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _log_access = False

    _order = 'date_created DESC, date_done DESC'

    _removal_interval = 30  # days
    _default_related_action = 'related_action_open_record'

    uuid = fields.Char(string='UUID',
                       readonly=True,
                       index=True,
                       required=True)
    user_id = fields.Many2one(comodel_name='res.users',
                              string='User ID',
                              required=True)
    company_id = fields.Many2one(comodel_name='res.company',
                                 string='Company', index=True)
    name = fields.Char(string='Description', readonly=True)

    model_name = fields.Char(string='Model', readonly=True)
    method_name = fields.Char(readonly=True)
    record_ids = Serialized(readonly=True)
    args = JobSerialized(readonly=True)
    kwargs = JobSerialized(readonly=True)
    func_string = fields.Char(string='Task', compute='_compute_func_string',
                              readonly=True, store=True)

    state = fields.Selection(STATES,
                             readonly=True,
                             required=True,
                             index=True)
    priority = fields.Integer()
    exc_info = fields.Text(string='Exception Info', readonly=True)
    result = fields.Text(readonly=True)

    date_created = fields.Datetime(string='Created Date', readonly=True)
    date_started = fields.Datetime(string='Start Date', readonly=True)
    date_enqueued = fields.Datetime(string='Enqueue Time', readonly=True)
    date_done = fields.Datetime(readonly=True)

    eta = fields.Datetime(string='Execute only after')
    retry = fields.Integer(string='Current try')
    max_retries = fields.Integer(
        string='Max. retries',
        help="The job will fail if the number of tries reach the "
             "max. retries.\n"
             "Retries are infinite when empty.",
    )
    channel_method_name = fields.Char(readonly=True,
                                      compute='_compute_job_function',
                                      store=True)
    job_function_id = fields.Many2one(comodel_name='queue.job.function',
                                      compute='_compute_job_function',
                                      string='Job Function',
                                      readonly=True,
                                      store=True)

    override_channel = fields.Char()
    channel = fields.Char(compute='_compute_channel',
                          inverse='_inverse_channel',
                          store=True,
                          index=True)

    identity_key = fields.Char()

    @api.model_cr
    def init(self):
        self._cr.execute(
            'SELECT indexname FROM pg_indexes WHERE indexname = %s ',
            ('queue_job_identity_key_state_partial_index',)
        )
        if not self._cr.fetchone():
            self._cr.execute(
                "CREATE INDEX queue_job_identity_key_state_partial_index "
                "ON queue_job (identity_key) WHERE state in ('pending', "
                "'enqueued') AND identity_key IS NOT NULL;"
            )

    @api.multi
    def _inverse_channel(self):
        for record in self:
            record.override_channel = record.channel

    @api.multi
    @api.depends('job_function_id.channel_id')
    def _compute_channel(self):
        for record in self:
            record.channel = (record.override_channel or
                              record.job_function_id.channel)

    @api.multi
    @api.depends('model_name', 'method_name', 'job_function_id.channel_id')
    def _compute_job_function(self):
        for record in self:
            model = self.env[record.model_name]
            method = getattr(model, record.method_name)
            channel_method_name = channel_func_name(model, method)
            func_model = self.env['queue.job.function']
            function = func_model.search([('name', '=', channel_method_name)])
            record.channel_method_name = channel_method_name
            record.job_function_id = function

    @api.multi
    @api.depends('model_name', 'method_name', 'record_ids', 'args', 'kwargs')
    def _compute_func_string(self):
        for record in self:
            record_ids = record.record_ids
            model = repr(self.env[record.model_name].browse(record_ids))
            args = [repr(arg) for arg in record.args]
            kwargs = ['%s=%r' % (key, val) for key, val
                      in record.kwargs.items()]
            all_args = ', '.join(args + kwargs)
            record.func_string = (
                "%s.%s(%s)" % (model, record.method_name, all_args)
            )

    @api.multi
    def open_related_action(self):
        """Open the related action associated to the job"""
        self.ensure_one()
        job = Job.load(self.env, self.uuid)
        action = job.related_action()
        if action is None:
            raise exceptions.UserError(_('No action available for this job'))
        return action

    @api.multi
    def _change_job_state(self, state, result=None):
        """Change the state of the `Job` object

        Changing the state of the Job will automatically change some fields
        (date, result, ...).
        """
        for record in self:
            job_ = Job.load(record.env, record.uuid)
            if state == DONE:
                job_.set_done(result=result)
            elif state == PENDING:
                job_.set_pending(result=result)
            else:
                raise ValueError('State not supported: %s' % state)
            job_.store()

    @api.multi
    def button_done(self):
        result = _('Manually set to done by %s') % self.env.user.name
        self._change_job_state(DONE, result=result)
        return True

    @api.multi
    def requeue(self):
        self._change_job_state(PENDING)
        return True

    def _message_post_on_failure(self):
        # subscribe the users now to avoid to subscribe them
        # at every job creation
        domain = self._subscribe_users_domain()
        users = self.env['res.users'].search(domain)
        self.message_subscribe(partner_ids=users.mapped('partner_id').ids)
        for record in self:
            msg = record._message_failed_job()
            if msg:
                record.message_post(body=msg,
                                    subtype='queue_job.mt_job_failed')

    @api.multi
    def write(self, vals):
        res = super(QueueJob, self).write(vals)
        if vals.get('state') == 'failed':
            self._message_post_on_failure()
        return res

    @api.multi
    def _subscribe_users_domain(self):
        """Subscribe all users having the 'Queue Job Manager' group"""
        group = self.env.ref('queue_job.group_queue_job_manager')
        if not group:
            return None
        companies = self.mapped('company_id')
        domain = [('groups_id', '=', group.id)]
        if companies:
            domain.append(('company_id', 'child_of', companies.ids))
        return domain

    @api.multi
    def _message_failed_job(self):
        """Return a message which will be posted on the job when it is failed.

        It can be inherited to allow more precise messages based on the
        exception informations.

        If nothing is returned, no message will be posted.
        """
        self.ensure_one()
        return _("Something bad happened during the execution of the job. "
                 "More details in the 'Exception Information' section.")

    @api.model
    def _needaction_domain_get(self):
        """Returns the domain to filter records that require an action

        :return: domain or False is no action
        """
        return [('state', '=', 'failed')]

    @api.model
    def autovacuum(self):
        """Delete all jobs done since more than ``_removal_interval`` days.

        Called from a cron.
        """
        deadline = datetime.now() - timedelta(days=self._removal_interval)
        jobs = self.search(
            [('date_done', '<=', deadline)],
        )
        jobs.unlink()
        return True

    @api.multi
    def related_action_open_record(self):
        """Open a form view with the record(s) of the job.

        For instance, for a job on a ``product.product``, it will open a
        ``product.product`` form view with the product record(s) concerned by
        the job. If the job concerns more than one record, it opens them in a
        list.

        This is the default related action.

        """
        self.ensure_one()
        model_name = self.model_name
        records = self.env[model_name].browse(self.record_ids).exists()
        if not records:
            return None
        action = {
            'name': _('Related Record'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': records._name,
        }
        if len(records) == 1:
            action['res_id'] = records.id
        else:
            action.update({
                'name': _('Related Records'),
                'view_mode': 'tree,form',
                'domain': [('id', 'in', records.ids)],
            })
        return action


class RequeueJob(models.TransientModel):
    _name = 'queue.requeue.job'
    _description = 'Wizard to requeue a selection of jobs'

    @api.model
    def _default_job_ids(self):
        res = False
        context = self.env.context
        if (context.get('active_model') == 'queue.job' and
                context.get('active_ids')):
            res = context['active_ids']
        return res

    job_ids = fields.Many2many(comodel_name='queue.job',
                               string='Jobs',
                               default=_default_job_ids)

    @api.multi
    def requeue(self):
        jobs = self.job_ids
        jobs.requeue()
        return {'type': 'ir.actions.act_window_close'}


class SetJobsToDone(models.TransientModel):
    _inherit = 'queue.requeue.job'
    _name = 'queue.jobs.to.done'
    _description = 'Set all selected jobs to done'

    @api.multi
    def set_done(self):
        jobs = self.job_ids
        jobs.button_done()
        return {'type': 'ir.actions.act_window_close'}


class JobChannel(models.Model):
    _name = 'queue.job.channel'
    _description = 'Job Channels'

    name = fields.Char()
    complete_name = fields.Char(compute='_compute_complete_name',
                                store=True,
                                readonly=True)
    parent_id = fields.Many2one(comodel_name='queue.job.channel',
                                string='Parent Channel',
                                ondelete='restrict')
    job_function_ids = fields.One2many(comodel_name='queue.job.function',
                                       inverse_name='channel_id',
                                       string='Job Functions')

    _sql_constraints = [
        ('name_uniq',
         'unique(complete_name)',
         'Channel complete name must be unique'),
    ]

    @api.multi
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for record in self:
            if not record.name:
                continue  # new record
            channel = record
            parts = [channel.name]
            while channel.parent_id:
                channel = channel.parent_id
                parts.append(channel.name)
            record.complete_name = '.'.join(reversed(parts))

    @api.multi
    @api.constrains('parent_id', 'name')
    def parent_required(self):
        for record in self:
            if record.name != 'root' and not record.parent_id:
                raise exceptions.ValidationError(_('Parent channel required.'))

    @api.multi
    def write(self, values):
        for channel in self:
            if (not self.env.context.get('install_mode') and
                    channel.name == 'root' and
                    ('name' in values or 'parent_id' in values)):
                raise exceptions.Warning(_('Cannot change the root channel'))
        return super(JobChannel, self).write(values)

    @api.multi
    def unlink(self):
        for channel in self:
            if channel.name == 'root':
                raise exceptions.Warning(_('Cannot remove the root channel'))
        return super(JobChannel, self).unlink()

    @api.multi
    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, record.complete_name))
        return result


class JobFunction(models.Model):
    _name = 'queue.job.function'
    _description = 'Job Functions'
    _log_access = False

    @api.model
    def _default_channel(self):
        return self.env.ref('queue_job.channel_root')

    name = fields.Char(index=True)
    channel_id = fields.Many2one(comodel_name='queue.job.channel',
                                 string='Channel',
                                 required=True,
                                 default=_default_channel)
    channel = fields.Char(related='channel_id.complete_name',
                          store=True,
                          readonly=True)

    @api.model
    def _find_or_create_channel(self, channel_path):
        channel_model = self.env['queue.job.channel']
        parts = channel_path.split('.')
        parts.reverse()
        channel_name = parts.pop()
        assert channel_name == 'root', "A channel path starts with 'root'"
        # get the root channel
        channel = channel_model.search([('name', '=', channel_name)])
        while parts:
            channel_name = parts.pop()
            parent_channel = channel
            channel = channel_model.search([
                ('name', '=', channel_name),
                ('parent_id', '=', parent_channel.id),
            ], limit=1)
            if not channel:
                channel = channel_model.create({
                    'name': channel_name,
                    'parent_id': parent_channel.id,
                })
        return channel

    @api.model
    def _register_job(self, model, job_method):
        func_name = channel_func_name(model, job_method)
        if not self.search_count([('name', '=', func_name)]):
            channel = self._find_or_create_channel(job_method.default_channel)
            self.create({'name': func_name, 'channel_id': channel.id})
