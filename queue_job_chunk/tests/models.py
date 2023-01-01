# Copyright 2022 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


# Exemple of pure python processor (inherit is not possible)
class TestPythonPartnerProcessor:
    def __init__(self, chunk):
        super().__init__()
        self.env = chunk.env
        self.chunk = chunk

    def run(self):
        return self.env["res.partner"].create(self.chunk._get_data())


# Exemple of odoo processor (inherit is possible)
class TestOdooStateProcessor(models.TransientModel):
    _name = "test.odoo.state.processor"
    _description = "Chunk Processor State Create"

    chunk_id = fields.Many2one("queue.job.chunk", "Chunk")

    def run(self):
        return self.env["res.country.state"].create(self.chunk_id._get_data())


class QueueJobChunk(models.Model):
    _inherit = "queue.job.chunk"

    processor = fields.Selection(
        selection_add=[
            ("test_partner", "Test create Partner"),
            ("test_state", "Test create Country State"),
        ],
    )

    def _get_processor(self):
        if self.processor == "test_partner":
            return TestPythonPartnerProcessor(self)
        elif self.processor == "test_state":
            return self.env["test.odoo.state.processor"].new({"chunk_id": self.id})
