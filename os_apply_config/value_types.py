# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
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

import re

from os_apply_config import config_exception

TYPES = {
    "int": "^[0-9]+$",
    "default": "^[A-Za-z0-9_]*$",
    "netaddress": "^[A-Za-z0-9/.:-]*$",
    "netdevice": "^[A-Za-z0-9/.:-]*$",
    "dsn": "(?#driver)^[a-zA-Z0-9]+://"
           "(?#username[:password])([a-zA-Z0-9+_-]+(:[^@]+)?)?"
           "(?#@host or file)(@?[a-zA-Z0-9/_.-]+)?"
           "(?#/dbname)(/[a-zA-Z0-9_-]+)?"
           "(?#?variable=value)(\?[a-zA-Z0-9=_-]+)?$",
    "swiftdevices": "^(r\d+z\d+-[A-Za-z0-9.-_]+:%PORT%/[^,]+,?)+$",  # noqa W605
    "username": "^[A-Za-z0-9_-]+$",
    "raw": ""
}


def ensure_type(string_value, type_name='default'):
    if type_name not in TYPES:
        raise ValueError(
            "requested validation of unknown type: %s" % type_name)
    if not re.match(TYPES[type_name], string_value):
        exception = config_exception.ConfigException
        raise exception("cannot interpret value '%s' as type %s" % (
            string_value, type_name))
    return string_value
