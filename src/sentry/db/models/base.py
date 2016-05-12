"""
sentry.db.models
~~~~~~~~~~~~~~~~

:copyright: (c) 2010-2014 by the Sentry Team, see AUTHORS for more details.
:license: BSD, see LICENSE for more details.
"""

from __future__ import absolute_import

import logging

from django.db import models
from django.db.models import signals

from .fields.bounded import BoundedBigAutoField
from .manager import BaseManager
from .query import update

__all__ = ('BaseModel', 'Model', 'sane_repr', 'sane_dict')

UNSAVED = object()


def sane_repr(*attrs):
    if 'id' not in attrs and 'pk' not in attrs:
        attrs = ('id',) + attrs

    def _repr(self):
        cls = type(self)
        sane_attrs = attrs + getattr(cls, '__sane__', ())

        pairs = (
            '%s=%s' % (a, repr(getattr(self, a, None)))
            for a in sane_attrs)

        return u'<%s at 0x%x: %s>' % (cls.__name__, id(self), ', '.join(pairs))

    return _repr


def sane_dict(*attrs):
    if 'id' not in attrs and 'pk' not in attrs:
        attrs = ('id',) + attrs

    def _dict(self):
        cls = type(self)
        sane_attrs = attrs + getattr(cls, '__sane__', ())

        return {
            '%s.%s' % (cls.__name__.lower(), a): str(getattr(self, a, None))
            for a in sane_attrs
        }

    return _dict


class BaseModel(models.Model):
    class Meta:
        abstract = True

    objects = BaseManager()

    update = update

    def __init__(self, *args, **kwargs):
        super(BaseModel, self).__init__(*args, **kwargs)
        self._update_tracked_data()

    def __getstate__(self):
        d = self.__dict__.copy()
        # we cant serialize weakrefs
        d.pop('_Model__data', None)
        return d

    def __reduce__(self):
        (model_unpickle, stuff, _) = super(BaseModel, self).__reduce__()
        return (model_unpickle, stuff, self.__getstate__())

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._update_tracked_data()

    def __get_field_value(self, field):
        if isinstance(field, models.ForeignKey):
            return getattr(self, field.column, None)
        return getattr(self, field.name, None)

    def _update_tracked_data(self):
        "Updates a local copy of attributes values"
        if self.id:
            data = {}
            for f in self._meta.fields:
                try:
                    data[f.column] = self.__get_field_value(f)
                except AttributeError as e:
                    # this case can come up from pickling
                    logging.exception(unicode(e))
            self.__data = data
        else:
            self.__data = UNSAVED

    def has_changed(self, field_name):
        "Returns ``True`` if ``field`` has changed since initialization."
        if self.__data is UNSAVED:
            return False
        field = self._meta.get_field(field_name)
        return self.__data.get(field_name) != self.__get_field_value(field)

    def old_value(self, field_name):
        "Returns the previous value of ``field``"
        if self.__data is UNSAVED:
            return None
        return self.__data.get(field_name)


def __model_post_save(instance, **kwargs):
    if not isinstance(instance, BaseModel):
        return
    instance._update_tracked_data()


class Model(BaseModel):
    id = BoundedBigAutoField(primary_key=True)

    class Meta:
        abstract = True

    __sane__ = ('id')

    __sdict__ = sane_dict('id')


signals.post_save.connect(__model_post_save)
