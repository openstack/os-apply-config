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

import grp
import pwd

import testtools

from os_apply_config import config_exception as exc
from os_apply_config import oac_file


class OacFileTestCase(testtools.TestCase):
    def test_mode_string(self):
        oacf = oac_file.OacFile('')
        mode = '0644'
        try:
            oacf.mode = mode
        except exc.ConfigException as e:
            self.assertIn("mode '%s' is not numeric" % mode, str(e))

    def test_mode_range(self):
        oacf = oac_file.OacFile('')
        for mode in [-1, 0o1000]:
            try:
                oacf.mode = mode
            except exc.ConfigException as e:
                self.assertTrue("mode '%#o' out of range" % mode in str(e),
                                "mode: %#o" % mode)

        for mode in [0, 0o777]:
            oacf.mode = mode

    def test_owner_positive(self):
        oacf = oac_file.OacFile('')
        users = pwd.getpwall()
        for name in [user[0] for user in users]:
            oacf.owner = name
        for uid in [user[2] for user in users]:
            oacf.owner = uid

    def test_owner_negative(self):
        oacf = oac_file.OacFile('')
        try:
            user = -1
            oacf.owner = user
        except exc.ConfigException as e:
            self.assertIn(
                "owner '%s' not found in passwd database" % user, str(e))
        try:
            user = "za"
            oacf.owner = user
        except exc.ConfigException as e:
            self.assertIn(
                "owner '%s' not found in passwd database" % user, str(e))

    def test_group_positive(self):
        oacf = oac_file.OacFile('')
        groups = grp.getgrall()
        for name in [group[0] for group in groups]:
            oacf.group = name
        for gid in [group[2] for group in groups]:
            oacf.group = gid

    def test_group_negative(self):
        oacf = oac_file.OacFile('')
        try:
            group = -1
            oacf.group = group
        except exc.ConfigException as e:
            self.assertIn(
                "group '%s' not found in group database" % group, str(e))
        try:
            group = "za"
            oacf.group = group
        except exc.ConfigException as e:
            self.assertIn(
                "group '%s' not found in group database" % group, str(e))
