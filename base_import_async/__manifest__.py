# @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Asynchronous Import",
    "summary": "Import CSV files in the background",
    "version": "13.0.2.0.0",
    "author": "Akretion, ACSONE SA/NV, Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "https://github.com/OCA/queue",
    "category": "Generic Modules",
    "depends": ["base_import", "queue_job"],
    "data": ["data/queue_job_function_data.xml", "views/base_import_async.xml"],
    "qweb": ["static/src/xml/import.xml"],
    "installable": False,
    "development_status": "Production/Stable",
}
