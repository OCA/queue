# Copyright 2022 Ooops (https://ooops404.com).
# @author Ashish Hirpara <hello@ashish-hirpara.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

{
    "name": "Base import async lang",
    "summary": """Import by language - sets the job queue language to take into
    account users' language when importing, in order to search
    for records in that language""",
    "version": "14.0.1.0.0",
    "author": "Ashish Hirpara, Ooops, Odoo Community Association (OCA)",
    "contributors": ["Ashish Hirpara"],
    "maintainers": ["AshishHirapara"],
    "website": "https://github.com/OCA/queue",
    "license": "AGPL-3",
    "category": "Generic Modules",
    "depends": ["base_import_async"],
    "data": ["views/queue_job_view.xml"],
    "installable": True,
    "auto_install": False,
}
