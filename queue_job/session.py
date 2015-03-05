# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2012-2013 Camptocamp SA
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import logging
import threading
from contextlib import contextmanager

import openerp
from openerp.modules.registry import RegistryManager

from .deprecate import log_deprecate

_logger = logging.getLogger(__name__)


class ConnectorSessionHandler(object):
    """ Allow to create a new instance of
    :py:class:`~connector.session.ConnectorSession` for a database.

    .. attribute:: db_name

        The name of the database we're working on

    .. attribute:: uid

        The User ID as integer

    .. attribute:: context

        The current OpenERP's context

    Usage::

        session_hdl = ConnectorSessionHandler(db_name, 1)
        with session_hdl.session() as session:
            # work with session
    """

    def __init__(self, db_name, uid, context=None):
        self.db_name = db_name
        self.uid = uid
        self.context = {} if context is None else context

    @contextmanager
    def session(self):
        """ Context Manager: start a new session and ensure that the
        session's cursor is:

        * rollbacked on errors
        * commited at the end of the ``with`` context when no error occured
        * always closed at the end of the ``with`` context
        * it handles the registry signaling
        """
        with openerp.api.Environment.manage():
            db = openerp.sql_db.db_connect(self.db_name)
            session = ConnectorSession(db.cursor(),
                                       self.uid,
                                       context=self.context)

            try:
                RegistryManager.check_registry_signaling(self.db_name)
                yield session
                RegistryManager.signal_caches_change(self.db_name)
            except:
                session.rollback()
                raise
            else:
                session.commit()
            finally:
                session.close()


class ConnectorSession(object):
    """ Container for the OpenERP transactional stuff:

    .. attribute:: env

        The Environment

    .. attribute:: cr

        The OpenERP Cursor

    .. attribute:: uid

        The User ID as integer

    .. attribute:: pool

        The registry of models

    .. attribute:: context

        The current OpenERP's context
    """

    def __init__(self, cr, uid, context=None):
        if context is None:
            context = {}
        self.env = openerp.api.Environment(cr, uid, context)

    @property
    def cr(self):
        return self.env.cr

    @property
    def uid(self):
        return self.env.uid

    @property
    def context(self):
        return self.env.context

    @property
    def pool(self):
        return self.env.registry

    @contextmanager
    def change_user(self, uid):
        """ Context Manager: create a new Env with the specified user

        It generates a new :class:`openerp.api.Environment` used within
        the context manager, where the user is replaced by the specified
        one.  The original environment is restored at the closing of the
        context manager.

        .. warning:: only recordsets read within the context manager
                     will be attached to this environment. In many cases,
                     you will prefer to use
                     :meth:`openerp.models.BaseModel.with_context`
        """
        env = self.env
        self.env = env(user=uid)
        yield
        self.env = env

    @contextmanager
    def change_context(self, *args, **kwargs):
        """ Context Manager: create a new Env with an updated context

        It generates a new :class:`openerp.api.Environment` used within
        the context manager, where the context is extended with the
        arguments. The original environment is restored at the closing
        of the context manager.

        The extended context is either the provided ``context`` in which
        ``overrides`` are merged or the *current* context in which
        ``overrides`` are merged e.g.

        .. code-block:: python

            # current context is {'key1': True}
            r2 = records.with_context({}, key2=True)
            # -> r2._context is {'key2': True}
            r2 = records.with_context(key2=True)
            # -> r2._context is {'key1': True, 'key2': True}

        .. warning:: only recordsets read within the context manager
                     will be attached to this environment. In many cases,
                     you will prefer to use
                     :meth:`openerp.models.BaseModel.with_context`
        """
        context = dict(args[0] if args else self.context, **kwargs)
        env = self.env
        self.env = env(context=context)
        yield
        self.env = env

    def commit(self):
        """ Commit the cursor """
        # do never commit during tests
        if not getattr(threading.currentThread(), 'testing', False):
            self.cr.commit()

    def rollback(self):
        """ Rollback the cursor """
        self.cr.rollback()

    def close(self):
        """ Close the cursor """
        self.cr.close()

    def search(self, model, domain, limit=None, offset=0, order=None):
        """ Shortcut to :py:class:`openerp.models.BaseModel.search` """
        log_deprecate("'Session(...).search(...)' has been deprecated in "
                      "favor of 'Session(...).env['model'].search(...)'")
        return self.pool[model].search(self.cr, self.uid, domain,
                                       limit=limit, offset=offset,
                                       order=order, context=self.context)

    def browse(self, model, ids):
        """ Shortcut to :py:class:`openerp.models.BaseModel.browse` """
        model_obj = self.pool[model]
        log_deprecate("'Session(...).browse(...)' has been deprecated in "
                      "favor of 'Session(...).env['model'].browse(...)'")
        return model_obj.browse(self.cr, self.uid, ids, context=self.context)

    def read(self, model, ids, fields):
        """ Shortcut to :py:class:`openerp.models.BaseModel.read` """
        log_deprecate("'Session(...).read(...)' has been deprecated in "
                      "favor of 'Session(...).env['model'].read(...)'")
        return self.pool[model].read(self.cr, self.uid, ids, fields,
                                     context=self.context)

    def create(self, model, values):
        """ Shortcut to :py:class:`openerp.models.BaseModel.create` """
        log_deprecate("'Session(...).create(...)' has been deprecated in "
                      "favor of 'Session(...).env['model'].create(...)'")
        return self.pool[model].create(self.cr, self.uid, values,
                                       context=self.context)

    def write(self, model, ids, values):
        """ Shortcut to :py:class:`openerp.models.BaseModel.write` """
        log_deprecate("'Session(...).write(...)' has been deprecated in "
                      "favor of 'Session(...).env['model'].write(...)'")
        return self.pool[model].write(self.cr, self.uid, ids, values,
                                      context=self.context)

    def unlink(self, model, ids):
        model_obj = self.pool[model]
        _logger.warning("'Session.unlink()' has been deprecated, prefer "
                        "'self.env['model'].unlink()' or "
                        "self.recordset().unlink() if you are in a "
                        "ConnectorUnit.")
        return model_obj.unlink(self.cr, self.uid, ids, context=self.context)

    def __repr__(self):
        return '<Session db_name: %s, uid: %d, context: %s>' % (self.cr.dbname,
                                                                self.uid,
                                                                self.context)

    def is_module_installed(self, module_name):
        """ Indicates whether a module is installed or not
        on the current database.

        Use a convention established for the connectors addons:
        To know if a module is installed, it looks if an (abstract)
        model with name ``module_name.installed`` is loaded in the
        registry.
        """
        return bool(self.pool.get('%s.installed' % module_name))
