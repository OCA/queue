# Copyright 2013-2016 Camptocamp SA
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import ast
import logging
import re
from collections import namedtuple
from datetime import datetime, timedelta

from odoo import _, api, exceptions, fields, models, tools
from odoo.osv import expression

from ..fields import JobSerialized
from ..job import CANCELLED, DONE, PENDING, STATES, Job

_logger = logging.getLogger(__name__)


regex_job_function_name = re.compile(r"^<([0-9a-z_\.]+)>\.([0-9a-zA-Z_]+)$")


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""
    _name = 'queue.job'
    _description = 'Queue Job'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _log_access = False

    _order = 'date_created DESC, date_done DESC'

    _removal_interval = 30  # days
    _default_related_action = 'related_action_open_record'

    # This must be passed in a context key "_job_edit_sentinel" to write on
    # protected fields. It protects against crafting "queue.job" records from
    # RPC (e.g. on internal methods). When ``with_delay`` is used, the sentinel
    # is set.
    EDIT_SENTINEL = object()
    _protected_fields = (
        "uuid",
        "name",
        "date_created",
        "model_name",
        "method_name",
        "func_string",
        "channel_method_name",
        "job_function_id",
        "records",
        "args",
        "kwargs",
    )

    uuid = fields.Char(string='UUID',
                       readonly=True,
                       index=True,
                       required=True)
    user_id = fields.Many2one(comodel_name='res.users',
                              string='User ID')
    company_id = fields.Many2one(comodel_name='res.company',
                                 string='Company', index=True)
    name = fields.Char(string='Description', readonly=True)

    model_name = fields.Char(string='Model', readonly=True)
    method_name = fields.Char(readonly=True)
    # record_ids field is only for backward compatibility (e.g. used in related
    # actions), can be removed (replaced by "records") in 14.0
    record_ids = JobSerialized(compute="_compute_record_ids", base_type=list)
    records = JobSerialized(
        string="Record(s)", readonly=True, base_type=models.BaseModel,
    )
    args = JobSerialized(readonly=True, base_type=tuple)
    kwargs = JobSerialized(readonly=True, base_type=dict)
    func_string = fields.Char(string="Task", readonly=True)

    state = fields.Selection(STATES,
                             readonly=True,
                             required=True,
                             index=True)
    priority = fields.Integer()
    exc_name = fields.Char(string="Exception", readonly=True)
    exc_message = fields.Char(string="Exception Message", readonly=True)
    exc_info = fields.Text(string='Exception Info', readonly=True)
    result = fields.Text(readonly=True)

    date_created = fields.Datetime(string='Created Date', readonly=True)
    date_started = fields.Datetime(string='Start Date', readonly=True)
    date_enqueued = fields.Datetime(string='Enqueue Time', readonly=True)
    date_done = fields.Datetime(readonly=True)
    exec_time = fields.Float(
        string="Execution Time (avg)",
        group_operator="avg",
        help="Time required to execute this job in seconds. Average when grouped.",
    )
    date_cancelled = fields.Datetime(readonly=True)

    eta = fields.Datetime(string='Execute only after')
    retry = fields.Integer(string='Current try')
    max_retries = fields.Integer(
        string='Max. retries',
        help="The job will fail if the number of tries reach the "
             "max. retries.\n"
             "Retries are infinite when empty.",
    )

    # FIXME the name of this field is very confusing
    channel_method_name = fields.Char(readonly=True)
    job_function_id = fields.Many2one(comodel_name='queue.job.function',
                                      string='Job Function',
                                      readonly=True)

    channel = fields.Char(index=True)

    identity_key = fields.Char(readonly=True)
    worker_pid = fields.Integer(readonly=True)

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

    @api.depends("records")
    def _compute_record_ids(self):
        for record in self:
            record.record_ids = record.records.ids

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("_job_edit_sentinel") is not self.EDIT_SENTINEL:
            # Prevent to create a queue.job record "raw" from RPC.
            # ``with_delay()`` must be used.
            raise exceptions.AccessError(
                _("Queue jobs must be created by calling 'with_delay()'.")
            )
        return super(
            QueueJob,
            self.with_context(mail_create_nolog=True, mail_create_nosubscribe=True),
        ).create(vals_list)

    def write(self, vals):
        if self.env.context.get("_job_edit_sentinel") is not self.EDIT_SENTINEL:
            write_on_protected_fields = [
                fieldname for fieldname in vals if fieldname in self._protected_fields
            ]
            if write_on_protected_fields:
                raise exceptions.AccessError(
                    _("Not allowed to change field(s): {}").format(
                        write_on_protected_fields
                    )
                )

        different_user_jobs = self.browse()
        if vals.get("user_id"):
            different_user_jobs = self.filtered(
                lambda records: records.env.user.id != vals["user_id"]
            )

        if vals.get("state") == "failed":
            self._message_post_on_failure()

        result = super().write(vals)

        for record in different_user_jobs:
            # the user is stored in the env of the record, but we still want to
            # have a stored user_id field to be able to search/groupby, so
            # synchronize the env of records with user_id
            super(QueueJob, record).write(
                {"records": record.records.sudo(vals["user_id"])}
            )
        return result

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
            elif state == CANCELLED:
                job_.set_cancelled(result=result)
            else:
                raise ValueError('State not supported: %s' % state)
            job_.store()

    @api.multi
    def button_done(self):
        result = _('Manually set to done by %s') % self.env.user.name
        self._change_job_state(DONE, result=result)
        return True

    @api.multi
    def button_cancelled(self):
        result = _('Cancelled by %s') % self.env.user.name
        self._change_job_state(CANCELLED, result=result)
        return True

    @api.multi
    def requeue(self):
        self._change_job_state(PENDING)
        return True

    def _message_post_on_failure(self):
        # subscribe the users now to avoid to subscribe them
        # at every job creation
        domain = self._subscribe_users_domain()
        base_users = self.env["res.users"].search(domain)
        for record in self:
            users = base_users | record.user_id
            record.message_subscribe(partner_ids=users.mapped("partner_id").ids)
            msg = record._message_failed_job()
            if msg:
                record.message_post(body=msg,
                                    subtype='queue_job.mt_job_failed')

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
        """Delete all jobs done based on the removal interval defined on the
           channel

        Called from a cron.
        """
        for channel in self.env['queue.job.channel'].search([]):
            deadline = datetime.now() - timedelta(
                days=int(channel.removal_interval))
            jobs = self.search(
                ['|',
                 ('date_done', '<=', deadline),
                 ('date_cancelled', '<=', deadline),
                 ('channel', '=', channel.complete_name)],
            )
            if jobs:
                jobs.unlink()
        return True

    @api.model
    def requeue_stuck_jobs(self, enqueued_delta=5, started_delta=0):
        """Fix jobs that are in a bad states
        :param in_queue_delta: lookup time in minutes for jobs
                                that are in enqueued state

        :param started_delta: lookup time in minutes for jobs
                                that are in enqueued state,
                                0 means that it is not checked
        """
        self._get_stuck_jobs_to_requeue(
            enqueued_delta=enqueued_delta,
            started_delta=started_delta
        ).requeue()
        return True

    @api.model
    def _get_stuck_jobs_domain(self, queue_dl, started_dl):
        domain = []
        now = fields.datetime.now()
        if queue_dl:
            queue_dl = now - timedelta(minutes=queue_dl)
            domain.append([
                '&',
                ('date_enqueued', '<=', fields.Datetime.to_string(queue_dl)),
                ('state', '=', 'enqueued'),
            ])
        if started_dl:
            started_dl = now - timedelta(minutes=started_dl)
            domain.append([
                '&',
                ('date_started', '<=', fields.Datetime.to_string(started_dl)),
                ('state', '=', 'started'),
            ])
        if not domain:
            raise exceptions.ValidationError(
                _("If both parameters are 0, ALL jobs will be requeued!")
            )
        return expression.OR(domain)

    @api.model
    def _get_stuck_jobs_to_requeue(self, enqueued_delta, started_delta):
        job_model = self.env['queue.job']
        stuck_jobs = job_model.search(self._get_stuck_jobs_domain(
            enqueued_delta,
            started_delta,
        ))
        return stuck_jobs

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
        records = self.records.exists()
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

    def _test_job(self):
        _logger.info("Running test job.")


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


class SetJobsToCancelled(models.TransientModel):
    _inherit = 'queue.requeue.job'
    _name = 'queue.jobs.to.cancelled'
    _description = 'Cancel all selected jobs'

    @api.multi
    def set_cancelled(self):
        jobs = self.job_ids.filtered(
            lambda x: x.state in ('pending', 'failed', 'enqueued')
        )
        jobs.button_cancelled()
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
    removal_interval = fields.Integer(
        default=lambda self: self.env['queue.job']._removal_interval,
        required=True)

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

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        if self.env.context.get("install_mode"):
            # installing a module that creates a channel: rebinds the channel
            # to an existing one (likely we already had the channel created by
            # the @job decorator previously)
            new_vals_list = []
            for vals in vals_list:
                name = vals.get("name")
                parent_id = vals.get("parent_id")
                if name and parent_id:
                    existing = self.search(
                        [("name", "=", name), ("parent_id", "=", parent_id)]
                    )
                    if existing:
                        if not existing.get_metadata()[0].get("noupdate"):
                            existing.write(vals)
                        records |= existing
                        continue
                new_vals_list.append(vals)
            vals_list = new_vals_list
        records |= super().create(vals_list)
        return records

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

    JobConfig = namedtuple(
        "JobConfig",
        "channel "
        "retry_pattern "
        "related_action_enable "
        "related_action_func_name "
        "related_action_kwargs "
        "job_function_id ",
    )

    @api.model
    def _default_channel(self):
        return self.env.ref('queue_job.channel_root')

    name = fields.Char(
        compute="_compute_name", inverse="_inverse_name", index=True, store=True,
    )

    # model and method should be required, but the required flag doesn't
    # let a chance to _inverse_name to be executed
    model_id = fields.Many2one(
        comodel_name="ir.model", string="Model", ondelete="cascade"
    )
    method = fields.Char()

    channel_id = fields.Many2one(comodel_name='queue.job.channel',
                                 string='Channel',
                                 required=True,
                                 default=_default_channel)
    channel = fields.Char(related='channel_id.complete_name',
                          store=True,
                          readonly=True)
    retry_pattern = JobSerialized(string="Retry Pattern (serialized)", base_type=dict)
    edit_retry_pattern = fields.Text(
        string="Retry Pattern",
        compute="_compute_edit_retry_pattern",
        inverse="_inverse_edit_retry_pattern",
        help="Pattern expressing from the count of retries on retryable errors,"
        " the number of of seconds to postpone the next execution.\n"
        "Example: {1: 10, 5: 20, 10: 30, 15: 300}.\n"
        "See the module description for details.",
    )
    related_action = JobSerialized(string="Related Action (serialized)", base_type=dict)
    edit_related_action = fields.Text(
        string="Related Action",
        compute="_compute_edit_related_action",
        inverse="_inverse_edit_related_action",
        help="The action when the button *Related Action* is used on a job. "
        "The default action is to open the view of the record related "
        "to the job. Configured as a dictionary with optional keys: "
        "enable, func_name, kwargs.\n"
        "See the module description for details.",
    )

    @api.depends("model_id.model", "method")
    def _compute_name(self):
        for record in self:
            if not (record.model_id and record.method):
                record.name = ""
                continue
            record.name = self.job_function_name(record.model_id.model, record.method)

    def _inverse_name(self):
        groups = regex_job_function_name.match(self.name)
        if not groups:
            raise exceptions.UserError(_("Invalid job function: {}").format(self.name))
        model_name = groups.group(1)
        method = groups.group(2)
        model = self.env["ir.model"].search([("model", "=", model_name)], limit=1)
        if not model:
            raise exceptions.UserError(_("Model {} not found").format(model_name))
        self.model_id = model.id
        self.method = method

    @api.depends("retry_pattern")
    def _compute_edit_retry_pattern(self):
        for record in self:
            retry_pattern = record._parse_retry_pattern()
            record.edit_retry_pattern = str(retry_pattern)

    def _inverse_edit_retry_pattern(self):
        try:
            self.retry_pattern = ast.literal_eval(self.edit_retry_pattern or "{}")
        except (ValueError, TypeError):
            raise exceptions.UserError(self._retry_pattern_format_error_message())

    @api.depends("related_action")
    def _compute_edit_related_action(self):
        for record in self:
            record.edit_related_action = str(record.related_action)

    def _inverse_edit_related_action(self):
        try:
            self.related_action = ast.literal_eval(self.edit_related_action or "{}")
        except (ValueError, TypeError):
            raise exceptions.UserError(self._related_action_format_error_message())

    @staticmethod
    def job_function_name(model_name, method_name):
        return "<{}>.{}".format(model_name, method_name)

    # TODO deprecated by :job-no-decorator:
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

    def job_default_config(self):
        return self.JobConfig(
            channel="root",
            retry_pattern={},
            related_action_enable=True,
            related_action_func_name=None,
            related_action_kwargs={},
            job_function_id=None,
        )

    def _parse_retry_pattern(self):
        try:
            # as json can't have integers as keys and the field is stored
            # as json, convert back to int
            retry_pattern = {
                int(try_count): postpone_seconds
                for try_count, postpone_seconds in self.retry_pattern.items()
            }
        except ValueError:
            _logger.error(
                "Invalid retry pattern for job function %s,"
                " keys could not be parsed as integers, fallback"
                " to the default retry pattern.",
                self.name,
            )
            retry_pattern = {}
        return retry_pattern

    @tools.ormcache("name")
    def job_config(self, name):
        config = self.search([("name", "=", name)], limit=1)
        if not config:
            return self.job_default_config()
        retry_pattern = config._parse_retry_pattern()
        return self.JobConfig(
            channel=config.channel,
            retry_pattern=retry_pattern,
            related_action_enable=config.related_action.get("enable", True),
            related_action_func_name=config.related_action.get("func_name"),
            related_action_kwargs=config.related_action.get("kwargs"),
            job_function_id=config.id,
        )

    def _retry_pattern_format_error_message(self):
        return _(
            "Unexpected format of Retry Pattern for {}.\n"
            "Example of valid format:\n"
            "{{1: 300, 5: 600, 10: 1200, 15: 3000}}"
        ).format(self.name)

    @api.constrains("retry_pattern")
    def _check_retry_pattern(self):
        for record in self:
            retry_pattern = record.retry_pattern
            if not retry_pattern:
                continue

            all_values = list(retry_pattern) + list(retry_pattern.values())
            for value in all_values:
                try:
                    int(value)
                except ValueError:
                    raise exceptions.UserError(
                        record._retry_pattern_format_error_message()
                    )

    def _related_action_format_error_message(self):
        return _(
            "Unexpected format of Related Action for {}.\n"
            "Example of valid format:\n"
            '{{"enable": True, "func_name": "related_action_foo",'
            ' "kwargs" {{"limit": 10}}}}'
        ).format(self.name)

    @api.constrains("related_action")
    def _check_related_action(self):
        valid_keys = ("enable", "func_name", "kwargs")
        for record in self:
            related_action = record.related_action
            if not related_action:
                continue

            if any(key not in valid_keys for key in related_action):
                raise exceptions.UserError(
                    record._related_action_format_error_message()
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = self.browse()
        if self.env.context.get("install_mode"):
            # installing a module that creates a job function: rebinds the record
            # to an existing one (likely we already had the job function created by
            # the @job decorator previously)
            new_vals_list = []
            for vals in vals_list:
                name = vals.get("name")
                if name:
                    existing = self.search([("name", "=", name)], limit=1)
                    if existing:
                        if not existing.get_metadata()[0].get("noupdate"):
                            existing.write(vals)
                        records |= existing
                        continue
                new_vals_list.append(vals)
            vals_list = new_vals_list
        records |= super().create(vals_list)
        self.clear_caches()
        return records

    def write(self, values):
        res = super().write(values)
        self.clear_caches()
        return res

    def unlink(self):
        res = super().unlink()
        self.clear_caches()
        return res

    # TODO deprecated by :job-no-decorator:
    def _register_job(self, model, job_method):
        func_name = self.job_function_name(model._name, job_method.__name__)
        if not self.search_count([('name', '=', func_name)]):
            channel = self._find_or_create_channel(job_method.default_channel)
            self.create({'name': func_name, 'channel_id': channel.id})
