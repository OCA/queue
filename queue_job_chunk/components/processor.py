#  Copyright (c) Akretion 2020
#  License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo.addons.component.core import AbstractComponent


# DISCUSSION: abstractcomponent?
class Processor(AbstractComponent):
    _name = "processor"
    _inherit = "base"
    _collection = "collection.base"
