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
import tempfile

import fixtures
import testtools

from os_apply_config import apply_config
from os_apply_config import config_exception

# example template tree
TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')
TEMPLATE_PATHS = [
    "/etc/glance/script.conf",
    "/etc/keystone/keystone.conf"
]

# config for example tree
CONFIG = {
    "x": "foo",
    "y": False,
    "database": {
    "url": "sqlite:///blah"
    }
}

# config for example tree - with subhash
CONFIG_SUBHASH = {
    "OpenStack::Config": {
    "x": "foo",
    "database": {
        "url": "sqlite:///blah"
    }
    }
}

# expected output for example tree
OUTPUT = {
    "/etc/glance/script.conf": "foo\n",
    "/etc/keystone/keystone.conf": "[foo]\ndatabase = sqlite:///blah\n"
}


def main_path():
    return (
        os.path.dirname(os.path.realpath(__file__)) +
        '/../os_apply_config.py')


def template(relpath):
    return os.path.join(TEMPLATES, relpath[1:])


class TestRunOSConfigApplier(testtools.TestCase):

    def setUp(self):
        super(TestRunOSConfigApplier, self).setUp()
        self.useFixture(fixtures.NestedTempfile())
        self.stdout = self.useFixture(fixtures.StringStream('stdout')).stream
        self.useFixture(fixtures.MonkeyPatch('sys.stdout', self.stdout))
        stderr = self.useFixture(fixtures.StringStream('stderr')).stream
        self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))
        self.logger = self.useFixture(
            fixtures.FakeLogger(name="os-apply-config"))
        fd, self.path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG))
            t.flush()

    def test_print_key(self):
        self.assertEqual(0, apply_config.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'database.url', '--type', 'raw']))
        self.stdout.seek(0)
        self.assertEqual(CONFIG['database']['url'],
                         self.stdout.read().strip())
        self.assertEqual('', self.logger.output)

    def test_print_non_string_key(self):
        self.assertEqual(0, apply_config.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'y', '--type', 'raw']))
        self.stdout.seek(0)
        self.assertEqual(str(CONFIG['y']),
                         self.stdout.read().strip())
        self.assertEqual('', self.logger.output)

    def test_print_key_missing(self):
        self.assertEqual(1, apply_config.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'does.not.exist']))
        self.assertIn('does not exist', self.logger.output)

    def test_print_key_missing_default(self):
        self.assertEqual(0, apply_config.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'does.not.exist', '--key-default', '']))
        self.stdout.seek(0)
        self.assertEqual('', self.stdout.read().strip())
        self.assertEqual('', self.logger.output)

    def test_print_key_wrong_type(self):
        self.assertEqual(1, apply_config.main(
            ['os-apply-config.py', '--metadata', self.path, '--key',
             'x', '--type', 'int']))
        self.assertIn('cannot interpret value', self.logger.output)

    def test_print_templates(self):
        apply_config.main(['os-apply-config', '--print-templates'])
        self.stdout.seek(0)
        self.assertEqual(
            self.stdout.read().strip(), apply_config.TEMPLATES_DIR)
        self.assertEqual('', self.logger.output)

    def test_os_config_files(self):
        with tempfile.NamedTemporaryFile() as fake_os_config_files:
            with tempfile.NamedTemporaryFile() as fake_config:
                fake_config.write(json.dumps(CONFIG))
                fake_config.flush()
                fake_os_config_files.write(json.dumps([fake_config.name]))
                fake_os_config_files.flush()
                apply_config.main(['os-apply-config',
                                   '--key', 'database.url',
                                   '--type', 'raw',
                                   '--os-config-files',
                                   fake_os_config_files.name])
                self.stdout.seek(0)
                self.assertEqual(
                    CONFIG['database']['url'], self.stdout.read().strip())


class OSConfigApplierTestCase(testtools.TestCase):

    def setUp(self):
        super(OSConfigApplierTestCase, self).setUp()
        self.useFixture(fixtures.FakeLogger('os-apply-config'))
        self.useFixture(fixtures.NestedTempfile())

    def test_install_config(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG))
            t.flush()
        tmpdir = tempfile.mkdtemp()
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        for path, contents in OUTPUT.items():
            full_path = os.path.join(tmpdir, path[1:])
            assert os.path.exists(full_path)
            self.assertEqual(open(full_path).read(), contents)

    def test_install_config_subhash(self):
        fd, tpath = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG_SUBHASH))
            t.flush()
        tmpdir = tempfile.mkdtemp()
        apply_config.install_config(
            [tpath], TEMPLATES, tmpdir, False, 'OpenStack::Config')
        for path, contents in OUTPUT.items():
            full_path = os.path.join(tmpdir, path[1:])
            assert os.path.exists(full_path)
            self.assertEqual(open(full_path).read(), contents)

    def test_respect_file_permissions(self):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(CONFIG))
            t.flush()
        tmpdir = tempfile.mkdtemp()
        template = "/etc/keystone/keystone.conf"
        target_file = os.path.join(tmpdir, template[1:])
        os.makedirs(os.path.dirname(target_file))
        # File dosen't exist, use the default mode (644)
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        self.assertEqual(os.stat(target_file).st_mode, 0o100644)
        self.assertEqual(open(target_file).read(), OUTPUT[template])
        # Set a different mode:
        os.chmod(target_file, 0o600)
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        # The permissions should be preserved
        self.assertEqual(os.stat(target_file).st_mode, 0o100600)
        self.assertEqual(open(target_file).read(), OUTPUT[template])

    def test_build_tree(self):
        self.assertEqual(apply_config.build_tree(
            apply_config.template_paths(TEMPLATES), CONFIG), OUTPUT)

    def test_render_template(self):
        # execute executable files, moustache non-executables
        self.assertEqual(apply_config.render_template(template(
            "/etc/glance/script.conf"), {"x": "abc"}), "abc\n")
        self.assertRaises(
            config_exception.ConfigException,
            apply_config.render_template, template(
                "/etc/glance/script.conf"), {})

    def test_render_moustache(self):
        self.assertEqual(apply_config.render_moustache("ab{{x.a}}cd", {
                         "x": {"a": "123"}}), "ab123cd")

    def test_render_moustache_bad_key(self):
        self.assertEqual(apply_config.render_moustache("{{badkey}}", {}), u'')

    def test_render_executable(self):
        params = {"x": "foo"}
        self.assertEqual(apply_config.render_executable(template(
            "/etc/glance/script.conf"), params), "foo\n")

    def test_render_executable_failure(self):
        self.assertRaises(
            config_exception.ConfigException,
            apply_config.render_executable,
            template("/etc/glance/script.conf"), {})

    def test_template_paths(self):
        expected = map(lambda p: (template(p), p), TEMPLATE_PATHS)
        actual = apply_config.template_paths(TEMPLATES)
        expected.sort(key=lambda tup: tup[1])
        actual.sort(key=lambda tup: tup[1])
        self.assertEqual(actual, expected)

    def test_strip_hash(self):
        h = {'a': {'b': {'x': 'y'}}, "c": [1, 2, 3]}
        self.assertEqual(apply_config.strip_hash(h, 'a.b'), {'x': 'y'})
        self.assertRaises(config_exception.ConfigException,
                          apply_config.strip_hash, h, 'a.nonexistent')
        self.assertRaises(config_exception.ConfigException,
                          apply_config.strip_hash, h, 'a.c')
