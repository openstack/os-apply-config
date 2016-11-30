# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import grp
import pwd

import six

from os_apply_config import config_exception as exc


class OacFile(object):
    DEFAULTS = {
        'allow_empty': True,
        'mode': None,
        'owner': None,
        'group': None,
    }

    def __init__(self, body, **kwargs):
        super(OacFile, self).__init__()
        self.body = body

        for k, v in six.iteritems(self.DEFAULTS):
            setattr(self, '_' + k, v)

        for k, v in six.iteritems(kwargs):
            if not hasattr(self, k):
                raise exc.ConfigException(
                    "unrecognised file control key '%s'" % (k))
            setattr(self, k, v)

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        a = ["OacFile(%s" % repr(self.body)]
        for key, default in six.iteritems(self.DEFAULTS):
            value = getattr(self, key)
            if value != default:
                a.append("%s=%s" % (key, repr(value)))
        return ", ".join(a) + ")"

    def set(self, key, value):
        """Allows setting attrs as an expression rather than a statement."""
        setattr(self, key, value)
        return self

    @property
    def allow_empty(self):
        """Returns allow_empty.

        If True and body='', no file will be created and any existing
        file will be deleted.
        """
        return self._allow_empty

    @allow_empty.setter
    def allow_empty(self, value):
        if type(value) is not bool:
            raise exc.ConfigException(
                "allow_empty requires Boolean, got: '%s'" % value)
        self._allow_empty = value
        return self

    @property
    def mode(self):
        """The permissions to set on the file, EG 0755."""
        return self._mode

    @mode.setter
    def mode(self, v):
        """Pass in the mode to set on the file.

        EG 0644. Must be between 0 and 0777, the sticky bit is not supported.
        """
        if type(v) is not int:
            raise exc.ConfigException("mode '%s' is not numeric" % v)
        if not 0 <= v <= 0o777:
            raise exc.ConfigException("mode '%#o' out of range" % v)
        self._mode = v

    @property
    def owner(self):
        """The UID to set on the file, EG 'rabbitmq' or '501'."""
        return self._owner

    @owner.setter
    def owner(self, v):
        """Pass in the UID to set on the file.

        EG 'rabbitmq' or 501.
        """
        try:
            if type(v) is int:
                user = pwd.getpwuid(v)
            elif type(v) is str:
                user = pwd.getpwnam(v)
            else:
                raise exc.ConfigException(
                    "owner '%s' must be a string or int" % v)
        except KeyError:
            raise exc.ConfigException(
                "owner '%s' not found in passwd database" % v)
        self._owner = user[2]

    @property
    def group(self):
        """The GID to set on the file, EG 'rabbitmq' or '501'."""
        return self._group

    @group.setter
    def group(self, v):
        """Pass in the GID to set on the file.

        EG 'rabbitmq' or 501.
        """
        try:
            if type(v) is int:
                group = grp.getgrgid(v)
            elif type(v) is str:
                group = grp.getgrnam(v)
            else:
                raise exc.ConfigException(
                    "group '%s' must be a string or int" % v)
        except KeyError:
            raise exc.ConfigException(
                "group '%s' not found in group database" % v)
        self._group = group[2]
