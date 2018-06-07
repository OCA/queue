# © 2015 ABF OSIELL <http://osiell.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Queue - NSCA Client",
    "summary": "Send passive alerts to monitor your Odoo application.",
    "version": "11.0.1.0.0",
    "category": "Tools",
    "website": "http://github.com/OCA/server-tools",
    "author": "Creu Blanca, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        'queue_job',
        'nsca_client',
    ],
}
