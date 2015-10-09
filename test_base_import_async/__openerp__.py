# -*- coding: utf-8 -*-
###############################################################################
#
#   Module for OpenERP
#   Copyright (C) 2014 ACSONE SA/NV (http://acsone.eu).
#   @author Stéphane Bidoul <stephane.bidoul@acsone.eu>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
{
    'name': 'Test suite for base_import_async',
    'version': '8.0.1.0.0',
    'author': 'ACSONE SA/NV, Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'category': 'Generic Modules',
    'description': """Test suite for base_import_async.

    Normally you don't need to install this.
    """,
    'depends': [
        'base_import_async',
        'account',
    ],
    'installable': True,
    'application': False,
}
