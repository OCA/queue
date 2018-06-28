# copyright 2016 Camptocamp
# license agpl-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import json
from datetime import datetime, date

import dateutil

from odoo import fields, models


class JobSerialized(fields.Field):
    """Serialized fields provide the storage for sparse fields."""
    type = 'job_serialized'
    column_type = ('text', 'text')

    def convert_to_column(self, value, record, values=None):
        return json.dumps(value, cls=JobEncoder)

    def convert_to_cache(self, value, record, validate=True):
        # cache format: dict
        value = value or {}
        if isinstance(value, dict):
            return value
        return json.loads(value, cls=JobDecoder, env=record.env)


class JobEncoder(json.JSONEncoder):
    """Encode Odoo recordsets so that we can later recompose them"""

    def default(self, obj):
        if isinstance(obj, models.BaseModel):
            return {'_type': 'odoo_recordset',
                    'model': obj._name,
                    'ids': obj.ids,
                    'uid': obj.env.uid,
                    }
        elif isinstance(obj, datetime):
            return {'_type': 'datetime_isoformat',
                    'value': obj.isoformat()}
        elif isinstance(obj, date):
            return {'_type': 'date_isoformat',
                    'value': obj.isoformat()}
        return json.JSONEncoder.default(self, obj)


class JobDecoder(json.JSONDecoder):
    """Decode json, recomposing recordsets"""

    def __init__(self, *args, **kwargs):
        env = kwargs.pop('env')
        super(JobDecoder, self).__init__(
            object_hook=self.object_hook, *args, **kwargs
        )
        assert env
        self.env = env

    def object_hook(self, obj):
        if '_type' not in obj:
            return obj
        type_ = obj['_type']
        if type_ == 'odoo_recordset':
            model = self.env[obj['model']]
            if obj.get('uid'):
                model = model.sudo(obj['uid'])
            return model.browse(obj['ids'])
        elif type_ == 'datetime_isoformat':
            return dateutil.parser.parse(obj['value'])
        elif type_ == 'date_isoformat':
            return dateutil.parser.parse(obj['value']).date()
        return obj
