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

import json
import os

import fixtures
import testtools

from os_apply_config import collect_config
from os_apply_config import config_exception as exc


class OCCTestCase(testtools.TestCase):
    def test_collect_config(self):
        conflict_configs = [('ec2', {'local-ipv4': '192.0.2.99',
                                     'instance-id': 'feeddead'}),
                            ('cfn', {'foo': {'bar': 'foo-bar'},
                                     'local-ipv4': '198.51.100.50'})]
        config_files = []
        tdir = self.useFixture(fixtures.TempDir())
        for name, config in conflict_configs:
            path = os.path.join(tdir.path, '%s.json' % name)
            with open(path, 'w') as out:
                out.write(json.dumps(config))
            config_files.append(path)
        config = collect_config.collect_config(config_files)
        self.assertEqual(
            {'local-ipv4': '198.51.100.50',
             'instance-id': 'feeddead',
             'foo': {'bar': 'foo-bar'}}, config)

    def test_collect_config_fallback(self):
        tdir = self.useFixture(fixtures.TempDir())
        with open(os.path.join(tdir.path, 'does_exist.json'), 'w') as t:
            t.write(json.dumps({'a': 1}))
        noexist_path = os.path.join(tdir.path, 'does_not_exist.json')

        config = collect_config.collect_config([], [noexist_path, t.name])
        self.assertEqual({'a': 1}, config)

        with open(os.path.join(tdir.path, 'does_exist_new.json'), 'w') as t2:
            t2.write(json.dumps({'a': 2}))

        config = collect_config.collect_config([t2.name], [t.name])
        self.assertEqual({'a': 2}, config)

        config = collect_config.collect_config([], [t.name, noexist_path])
        self.assertEqual({'a': 1}, config)
        self.assertEqual({},
                         collect_config.collect_config([], [noexist_path]))
        self.assertEqual({},
                         collect_config.collect_config([]))

    def test_failed_read(self):
        tdir = self.useFixture(fixtures.TempDir())
        unreadable_path = os.path.join(tdir.path, 'unreadable.json')
        with open(unreadable_path, 'w') as u:
            u.write(json.dumps({}))
        os.chmod(unreadable_path, 0o000)
        self.assertRaises(
            exc.ConfigException,
            lambda: list(collect_config.read_configs([unreadable_path])))

    def test_bad_json(self):
        tdir = self.useFixture(fixtures.TempDir())
        bad_json_path = os.path.join(tdir.path, 'bad.json')
        self.assertRaises(
            exc.ConfigException,
            lambda: list(collect_config.parse_configs([('{', bad_json_path)])))


class TestMergeConfigs(testtools.TestCase):

    def test_merge_configs_noconflict(self):
        noconflict_configs = [{'a': '1'},
                              {'b': 'Y'}]
        result = collect_config.merge_configs(noconflict_configs)
        self.assertEqual({'a': '1',
                          'b': 'Y'}, result)

    def test_merge_configs_conflict(self):
        conflict_configs = [{'a': '1'}, {'a': 'Z'}]
        result = collect_config.merge_configs(conflict_configs)
        self.assertEqual({'a': 'Z'}, result)

    def test_merge_configs_deep_conflict(self):
        deepconflict_conf = [{'a': '1'},
                             {'b': {'x': 'foo-bar', 'y': 'tribbles'}},
                             {'b': {'x': 'shazam'}}]
        result = collect_config.merge_configs(deepconflict_conf)
        self.assertEqual({'a': '1',
                          'b': {'x': 'shazam', 'y': 'tribbles'}}, result)

    def test_merge_configs_type_conflict(self):
        type_conflict = [{'a': 1}, {'a': [7, 8, 9]}]
        result = collect_config.merge_configs(type_conflict)
        self.assertEqual({'a': [7, 8, 9]}, result)

    def test_merge_configs_list_conflict(self):
        list_conflict = [{'a': [1, 2, 3]},
                         {'a': [4, 5, 6]}]
        result = collect_config.merge_configs(list_conflict)
        self.assertEqual({'a': [4, 5, 6]}, result)

    def test_merge_configs_empty_notdict(self):
        list_conflict = [[], {'a': '1'}, '', None, {'b': '2'}, {}]
        result = collect_config.merge_configs(list_conflict)
        self.assertEqual({'a': '1', 'b': '2'}, result)
