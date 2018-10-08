# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import mock
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.addons.queue_job.job import Job


class TestMailMail(TransactionCase):
    """
    Tests for mail.mail
    """

    def setUp(self):
        super().setUp()
        self.mail_obj = self.env['mail.mail']
        self.partner = self.env.ref("base.res_partner_2")
        self.queue_obj = self.env['queue.job']
        self.job_fct = "_send_mail_jobified"
        self.prepare_job_fct = "_send_email_delay"
        self.job_path = "odoo.addons.mail_queue_job.models." \
                        "mail_mail.MailMail.%s" % self.job_fct
        self.prepare_job_path = "odoo.addons.mail_queue_job.models." \
                                "mail_mail.MailMail.%s" % self.prepare_job_fct
        self.description = "Delayed email send %"

    def _get_related_jobs(self, existing_jobs, mail, now):
        """

        :param existing_jobs: queue.job recordset
        :param mail: mail.mail recordset
        :param now: date (str)
        :return: queue.job recordset
        """
        new_jobs = self.queue_obj.search([
            ('id', 'not in', existing_jobs.ids),
            ('model_name', '=', mail._name),
            ('method_name', '=', self.job_fct),
            ('priority', '=', mail.mail_job_priority),
            ('name', 'ilike', self.description),
            ('date_created', '>=', now),
        ])
        return new_jobs

    def _execute_real_job(self, queue_job):
        """
        Load and execute the given queue_job.
        Also refresh the queue_job to have updated fields
        :param queue_job: queue.job recordset
        :return: Job object
        """
        real_job = Job.load(queue_job.env, queue_job.uuid)
        real_job.perform()
        real_job.set_done()
        real_job.store()
        queue_job.refresh()
        return real_job

    def test_notify_creation(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is correctly triggered and pass into the
        listener on_record_create().
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'state': 'outgoing',
            'partner_ids': [(4, self.partner.id, False)],
        }
        with mock.patch(self.job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail = self.mail_obj.create(values)
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 1)
            self._execute_real_job(new_job)
            self.assertEquals(new_job.state, 'done')
            self.assertEqual(magic.call_count, 1)

    def test_notify_creation_skipped(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is not triggered and don't pass into the
        listener on_record_create().
        Skipped due to the state who is not 'outgoing'.
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'cancel',
        }
        with mock.patch(self.prepare_job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail = self.mail_obj.create(values)
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 0)
            self.assertEqual(magic.call_count, 1)

    def test_notify_write(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is correctly triggered and pass into the
        listener on_record_write().
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
        }
        existing_jobs = self.queue_obj.search([])
        now1 = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        new_job1 = self._get_related_jobs(existing_jobs, mail, now1)
        with mock.patch(self.job_path, autospec=True) as magic:
            magic.delayable = True
            now2 = fields.Datetime.now()
            mail.write({
                'subject': 'another subject',
            })
            new_job2 = self._get_related_jobs(existing_jobs, mail, now2)
            # A second job shouldn't be created on the write, because the
            # create already make a job
            self.assertEquals(new_job2, new_job1)
            # So we should have the job from the create
            self.assertEquals(len(new_job1), 1)
            self._execute_real_job(new_job1)
            self.assertEquals(new_job1.state, 'done')
            self.assertEqual(magic.call_count, 1)

    def test_notify_write_skipped(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is not triggered and don't pass into the
        listener on_record_write().
        Skipped due to the state who is not 'outgoing'.
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'cancel',
        }
        mail = self.mail_obj.create(values)
        with mock.patch(self.prepare_job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail.write({
                'subject': 'another subject',
            })
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 0)
            self.assertEqual(magic.call_count, 1)

    def test_job_during_create(self):
        """
        Test if during the creation of a mail.mail, a job is correctly
        triggered with the correct priority and correct description
        :return:
        """
        priority = 25
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
            'mail_job_priority': priority,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        # Ensure the priority is correct before continue
        self.assertEquals(mail.mail_job_priority, priority)
        new_jobs = self._get_related_jobs(existing_jobs, mail, now)
        self.assertEquals(len(new_jobs), 1)

    def test_job_during_create_skipped(self):
        """
        Test if during the creation of a mail.mail, a job is not
        triggered/created (because the state of the mail.mail is not
        'outgoing'.
        :return:
        """
        priority = 25
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'cancel',
            'mail_job_priority': priority,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        # Ensure the priority is correct before continue
        self.assertEquals(mail.mail_job_priority, priority)
        new_jobs = self._get_related_jobs(existing_jobs, mail, now)
        self.assertEquals(len(new_jobs), 0)

    def test_mail_no_exists(self):
        """
        Test the queue job when the mail.mail doesn't exists
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
            'mail_job_priority': 20,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        new_job = self._get_related_jobs(existing_jobs, mail, now)
        new_job.write({
            'record_ids': [mail.id + 1000],
        })
        self.assertEquals(len(new_job), 1)
        self._execute_real_job(new_job)
        self.assertFalse(bool(new_job.exc_info))
        self.assertEquals(new_job.state, 'done')

    def test_job_duplicate(self):
        """
        Test the specific case, when we have 2 jobs for a same mail.mail.
        One of the 2 jobs should not be executed.
        Steps:
        - Create 1 mail.mail
        - 1 new job should be created
        - Create a second mail.mail
        - Another job should be created
        - Copy the identity_key of the first into the second
        - Then execute the first job
        - Now execute the second job
        - We should have only 1 call (one of them should be aborted)
        :return:
        """
        priority = 25
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
            'mail_job_priority': priority,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail1 = self.mail_obj.create(values)
        new_job1 = self._get_related_jobs(existing_jobs, mail1, now)
        # Re-simulate the creation on same mail.mail
        mail1._send_email_delay(operation='create')
        # Only 1 job created/found
        self.assertEquals(len(new_job1), 1)
        existing_jobs |= new_job1
        new_job2 = self._get_related_jobs(existing_jobs, mail1, now)
        # No new job created
        self.assertEquals(len(new_job2), 0)
        # But still 2 different jobs
        self.assertNotEqual(new_job1, new_job2)
        with mock.patch(self.job_path, autospec=True) as magic:
            magic.delayable = True
            # Call the original job
            self._execute_real_job(new_job1)
            self.assertEquals(new_job1.state, 'done')
            self.assertEqual(magic.call_count, 1)
