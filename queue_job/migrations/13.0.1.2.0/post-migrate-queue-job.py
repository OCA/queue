# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        rule = env.ref("queue_job.queue_job_comp_rule", raise_if_not_found=False)
        if rule:
            domain = """[
                '|',
                ('company_id', '=', False),
                ('company_id', 'in', company_ids)
            ]"""
            values = {
                "domain_force": domain,
            }
            rule.write(values)
