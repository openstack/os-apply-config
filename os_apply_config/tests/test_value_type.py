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

import testtools

from os_apply_config import config_exception
from os_apply_config import value_types


class ValueTypeTestCase(testtools.TestCase):

    def test_unknown_type(self):
        self.assertRaises(
            ValueError, value_types.ensure_type, "foo", "badtype")

    def test_int(self):
        self.assertEqual("123", value_types.ensure_type("123", "int"))

    def test_default(self):
        self.assertEqual("foobar",
                         value_types.ensure_type("foobar", "default"))
        self.assertEqual("x86_64",
                         value_types.ensure_type("x86_64", "default"))

    def test_default_bad(self):
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type, "foo\nbar", "default")

    def test_default_empty(self):
        self.assertEqual('',
                         value_types.ensure_type('', 'default'))

    def test_raw_empty(self):
        self.assertEqual('',
                         value_types.ensure_type('', 'raw'))

    def test_net_address_ipv4(self):
        self.assertEqual('192.0.2.1', value_types.ensure_type('192.0.2.1',
                                                              'netaddress'))

    def test_net_address_cidr(self):
        self.assertEqual('192.0.2.0/24',
                         value_types.ensure_type('192.0.2.0/24', 'netaddress'))

    def test_ent_address_ipv6(self):
        self.assertEqual('::', value_types.ensure_type('::', 'netaddress'))
        self.assertEqual('2001:db8::2:1', value_types.ensure_type(
            '2001:db8::2:1', 'netaddress'))

    def test_net_address_dns(self):
        self.assertEqual('host.0domain-name.test',
                         value_types.ensure_type('host.0domain-name.test',
                                                 'netaddress'))

    def test_net_address_empty(self):
        self.assertEqual('', value_types.ensure_type('', 'netaddress'))

    def test_net_address_bad(self):
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type, "192.0.2.1;DROP TABLE foo",
                          'netaddress')

    def test_netdevice(self):
        self.assertEqual('eth0',
                         value_types.ensure_type('eth0', 'netdevice'))

    def test_netdevice_dash(self):
        self.assertEqual('br-ctlplane',
                         value_types.ensure_type('br-ctlplane', 'netdevice'))

    def test_netdevice_alias(self):
        self.assertEqual('eth0:1',
                         value_types.ensure_type('eth0:1', 'netdevice'))

    def test_netdevice_bad(self):
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type, "br-tun; DROP TABLE bar",
                          'netdevice')

    def test_dsn_nopass(self):
        test_dsn = 'mysql://user@host/db'
        self.assertEqual(test_dsn, value_types.ensure_type(test_dsn, 'dsn'))

    def test_dsn(self):
        test_dsn = 'mysql://user:pass@host/db'
        self.assertEqual(test_dsn, value_types.ensure_type(test_dsn, 'dsn'))

    def test_dsn_set_variables(self):
        test_dsn = 'mysql://user:pass@host/db?charset=utf8'
        self.assertEqual(test_dsn, value_types.ensure_type(test_dsn, 'dsn'))

    def test_dsn_sqlite_memory(self):
        test_dsn = 'sqlite://'
        self.assertEqual(test_dsn, value_types.ensure_type(test_dsn, 'dsn'))

    def test_dsn_sqlite_file(self):
        test_dsn = 'sqlite:///tmp/foo.db'
        self.assertEqual(test_dsn, value_types.ensure_type(test_dsn, 'dsn'))

    def test_dsn_bad(self):
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type,
                          "mysql:/user:pass@host/db?charset=utf8", 'dsn')
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type,
                          "mysql://user:pass@host/db?charset=utf8;DROP TABLE "
                          "foo", 'dsn')

    def test_swiftdevices_single(self):
        test_swiftdevices = 'r1z1-127.0.0.1:%PORT%/d1'
        self.assertEqual(test_swiftdevices, value_types.ensure_type(
                         test_swiftdevices,
                         'swiftdevices'))

    def test_swiftdevices_multi(self):
        test_swiftdevices = 'r1z1-127.0.0.1:%PORT%/d1,r1z1-127.0.0.1:%PORT%/d2'
        self.assertEqual(test_swiftdevices, value_types.ensure_type(
                         test_swiftdevices,
                         'swiftdevices'))

    def test_swiftdevices_blank(self):
        test_swiftdevices = ''
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type,
                          test_swiftdevices,
                          'swiftdevices')

    def test_swiftdevices_bad(self):
        test_swiftdevices = 'rz1-127.0.0.1:%PORT%/d1'
        self.assertRaises(config_exception.ConfigException,
                          value_types.ensure_type,
                          test_swiftdevices,
                          'swiftdevices')

    def test_username(self):
        for test_username in ['guest', 'guest_13-42']:
            self.assertEqual(test_username, value_types.ensure_type(
                             test_username,
                             'username'))

    def test_username_bad(self):
        for test_username in ['guest`ls`', 'guest$PASSWD', 'guest 2']:
            self.assertRaises(config_exception.ConfigException,
                              value_types.ensure_type,
                              test_username,
                              'username')
