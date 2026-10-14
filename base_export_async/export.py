# Copyright 2026 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import io

from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter
from odoo.tools.translate import _

from odoo.addons.web.controllers.export import ExportFormat, ExportXlsxWriter


class CleanedExportXlsxWriter(ExportXlsxWriter):
    def __init__(self, field_names, row_count=0, decimal_places=None):
        self.field_names = field_names
        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output, {"in_memory": True})
        self.base_style = self.workbook.add_format({"text_wrap": True})
        self.header_style = self.workbook.add_format({"bold": True})
        self.header_bold_style = self.workbook.add_format(
            {"text_wrap": True, "bold": True, "bg_color": "#e9ecef"}
        )
        self.date_style = self.workbook.add_format(
            {"text_wrap": True, "num_format": "yyyy-mm-dd"}
        )
        self.datetime_style = self.workbook.add_format(
            {"text_wrap": True, "num_format": "yyyy-mm-dd hh:mm:ss"}
        )
        self.worksheet = self.workbook.add_worksheet()
        self.value = False
        self.float_format = "#,##0.00"
        self.monetary_format = f'#,##0.{max(decimal_places or [2]) * "0"}'

        if row_count > self.worksheet.xls_rowmax:
            raise UserError(
                _(
                    f"There are too many rows ({row_count} rows, limit:"
                    f" {self.worksheet.xls_rowmax}) to export as Excel"
                    f"2007-2013 (.xlsx) format. Consider splitting the export."
                )
            )


class ExcelExport(ExportFormat):
    def __init__(self, env):
        self.env = env

    @property
    def content_type(self):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    @property
    def extension(self):
        return ".xlsx"

    def from_data(self, fields, rows):
        decimal_places = [
            res["decimal_places"]
            for res in self.env["res.currency"].search_read([], ["decimal_places"])
        ]
        with CleanedExportXlsxWriter(fields, len(rows), decimal_places) as xlsx_writer:
            for row_index, row in enumerate(rows):
                for cell_index, cell_value in enumerate(row):
                    xlsx_writer.write_cell(row_index + 1, cell_index, cell_value)

        return xlsx_writer.value
