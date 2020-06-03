#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

import ast

from odoo.addons.component.core import AbstractComponent, Component


class Processor(AbstractComponent):
    _name = "processor"
    _inherit = "base"
    _collection = "collection.base"


class Creator(
    Component
):  # TODO resolve issue with in-module component tests, move to test
    """ Just creates a record with given vals """

    _inherit = "base"
    _name = "basic.creator"
    _collection = "collection.base"
    _apply_on = ["res.partner", "ir.module.module"]
    _usage = "basic_create"

    def run(self, data):
        create_vals = ast.literal_eval(data)
        result = self.model.create(create_vals)
        return result
