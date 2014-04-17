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

import atexit
import json
import os
import tempfile

import fixtures
import mock
import testtools

from os_apply_config import apply_config
from os_apply_config import config_exception as exc

# example template tree
TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')
TEMPLATE_PATHS = [
    "/etc/glance/script.conf",
    "/etc/keystone/keystone.conf",
    "/etc/control/empty",
    "/etc/control/allow_empty",
    "/etc/control/mode",
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
    "/etc/glance/script.conf": apply_config.OacFile(
        "foo\n"),
    "/etc/keystone/keystone.conf": apply_config.OacFile(
        "[foo]\ndatabase = sqlite:///blah\n"),
    "/etc/control/empty": apply_config.OacFile(
        "foo\n"),
    "/etc/control/allow_empty": apply_config.OacFile(
        "").set('allow_empty', False),
    "/etc/control/mode": apply_config.OacFile(
        "lorem modus\n").set('mode', 0o755),
}


def main_path():
    return (
        os.path.dirname(os.path.realpath(__file__)) +
        '/../os_apply_config.py')


def template(relpath):
    return os.path.join(TEMPLATES, relpath[1:])


class TestRunOSConfigApplier(testtools.TestCase):
    """Tests the commandline options."""

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
                fake_config.write(json.dumps(CONFIG).encode('utf-8'))
                fake_config.flush()
                fake_os_config_files.write(
                    json.dumps([fake_config.name]).encode('utf-8'))
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
        self.logger = self.useFixture(fixtures.FakeLogger('os-apply-config'))
        self.useFixture(fixtures.NestedTempfile())

    def write_config(self, config):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'w') as t:
            t.write(json.dumps(config))
            t.flush()
        return path

    def check_output_file(self, tmpdir, path, obj):
        full_path = os.path.join(tmpdir, path[1:])
        if obj.allow_empty:
            assert os.path.exists(full_path), "%s doesn't exist" % path
            self.assertEqual(obj.body, open(full_path).read())
        else:
            assert not os.path.exists(full_path), "%s exists" % path

    def test_install_config(self):
        path = self.write_config(CONFIG)
        tmpdir = tempfile.mkdtemp()
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        for path, obj in OUTPUT.items():
            self.check_output_file(tmpdir, path, obj)

    def test_install_config_subhash(self):
        tpath = self.write_config(CONFIG_SUBHASH)
        tmpdir = tempfile.mkdtemp()
        apply_config.install_config(
            [tpath], TEMPLATES, tmpdir, False, 'OpenStack::Config')
        for path, obj in OUTPUT.items():
            self.check_output_file(tmpdir, path, obj)

    def test_delete_if_not_allowed_empty(self):
        path = self.write_config(CONFIG)
        tmpdir = tempfile.mkdtemp()
        template = "/etc/control/allow_empty"
        target_file = os.path.join(tmpdir, template[1:])
        # Touch the file
        os.makedirs(os.path.dirname(target_file))
        open(target_file, 'a').close()
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        # File should be gone
        self.assertFalse(os.path.exists(target_file))

    def test_respect_file_permissions(self):
        path = self.write_config(CONFIG)
        tmpdir = tempfile.mkdtemp()
        template = "/etc/keystone/keystone.conf"
        target_file = os.path.join(tmpdir, template[1:])
        os.makedirs(os.path.dirname(target_file))
        # File doesn't exist, use the default mode (644)
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        self.assertEqual(0o100644, os.stat(target_file).st_mode)
        self.assertEqual(OUTPUT[template].body, open(target_file).read())
        # Set a different mode:
        os.chmod(target_file, 0o600)
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        # The permissions should be preserved
        self.assertEqual(0o100600, os.stat(target_file).st_mode)
        self.assertEqual(OUTPUT[template].body, open(target_file).read())

    def test_build_tree(self):
        tree = apply_config.build_tree(
            apply_config.template_paths(TEMPLATES), CONFIG)
        self.assertEqual(OUTPUT, tree)

    def test_render_template(self):
        # execute executable files, moustache non-executables
        self.assertEqual("abc\n", apply_config.render_template(template(
            "/etc/glance/script.conf"), {"x": "abc"}))
        self.assertRaises(
            exc.ConfigException,
            apply_config.render_template,
            template("/etc/glance/script.conf"), {})

    def test_render_template_bad_template(self):
        tdir = self.useFixture(fixtures.TempDir())
        bt_path = os.path.join(tdir.path, 'bad_template')
        with open(bt_path, 'w') as bt:
            bt.write("{{#foo}}bar={{bar}}{{/bar}}")
        e = self.assertRaises(exc.ConfigException,
                              apply_config.render_template,
                              bt_path, {'foo': [{'bar':
                                                 'abc'}]})
        self.assertIn('could not render moustache template', str(e))
        self.assertIn('Section end tag mismatch', self.logger.output)

    def test_render_moustache(self):
        self.assertEqual(
            "ab123cd",
            apply_config.render_moustache("ab{{x.a}}cd", {"x": {"a": "123"}}))

    def test_render_moustache_bad_key(self):
        self.assertEqual(u'', apply_config.render_moustache("{{badkey}}", {}))

    def test_render_executable(self):
        params = {"x": "foo"}
        self.assertEqual("foo\n", apply_config.render_executable(
            template("/etc/glance/script.conf"), params))

    def test_render_executable_failure(self):
        self.assertRaises(
            exc.ConfigException,
            apply_config.render_executable,
            template("/etc/glance/script.conf"), {})

    def test_template_paths(self):
        expected = list(map(lambda p: (template(p), p), TEMPLATE_PATHS))
        actual = apply_config.template_paths(TEMPLATES)
        expected.sort(key=lambda tup: tup[1])
        actual.sort(key=lambda tup: tup[1])
        self.assertEqual(expected, actual)

    def test_strip_hash(self):
        h = {'a': {'b': {'x': 'y'}}, "c": [1, 2, 3]}
        self.assertEqual({'x': 'y'}, apply_config.strip_hash(h, 'a.b'))
        self.assertRaises(exc.ConfigException,
                          apply_config.strip_hash, h, 'a.nonexistent')
        self.assertRaises(exc.ConfigException,
                          apply_config.strip_hash, h, 'a.c')

    def test_load_list_from_json(self):
        def mkstemp():
            fd, path = tempfile.mkstemp()
            atexit.register(
                lambda: os.path.exists(path) and os.remove(path))
            return (fd, path)

        def write_contents(fd, contents):
            with os.fdopen(fd, 'w') as t:
                t.write(contents)
                t.flush()

        fd, path = mkstemp()
        load_list = apply_config.load_list_from_json
        self.assertRaises(ValueError, load_list, path)
        write_contents(fd, json.dumps(["/tmp/config.json"]))
        json_obj = load_list(path)
        self.assertEqual(["/tmp/config.json"], json_obj)
        os.remove(path)
        self.assertEqual([], load_list(path))

        fd, path = mkstemp()
        write_contents(fd, json.dumps({}))
        self.assertRaises(ValueError, load_list, path)

    def test_default_templates_dir_current(self):
        default = '/usr/libexec/os-apply-config/templates'
        with mock.patch('os.path.isdir', lambda x: x == default):
            self.assertEqual(default, apply_config.templates_dir())

    def test_default_templates_dir_deprecated(self):
        default = '/opt/stack/os-apply-config/templates'
        with mock.patch('os.path.isdir', lambda x: x == default):
            self.assertEqual(default, apply_config.templates_dir())

    def test_default_templates_dir_old_deprecated(self):
        default = '/opt/stack/os-config-applier/templates'
        with mock.patch('os.path.isdir', lambda x: x == default):
            self.assertEqual(default, apply_config.templates_dir())

    def test_default_templates_dir_both(self):
        default = '/usr/libexec/os-apply-config/templates'
        deprecated = '/opt/stack/os-apply-config/templates'
        with mock.patch('os.path.isdir', lambda x: (x == default or
                                                    x == deprecated)):
            self.assertEqual(default, apply_config.templates_dir())

    def test_control_mode(self):
        path = self.write_config(CONFIG)
        tmpdir = tempfile.mkdtemp()
        template = "/etc/control/mode"
        target_file = os.path.join(tmpdir, template[1:])
        apply_config.install_config([path], TEMPLATES, tmpdir, False)
        self.assertEqual(0o100755, os.stat(target_file).st_mode)

    def test_control_mode_string(self):
        oac_file = apply_config.OacFile('')
        mode = '0644'
        try:
            oac_file.mode = mode
        except exc.ConfigException as e:
            self.assertIn("mode '%s' is not numeric" % mode, str(e))

    def test_control_mode_range(self):
        oac_file = apply_config.OacFile('')
        for mode in [-1, 0o1000]:
            try:
                oac_file.mode = mode
            except exc.ConfigException as e:
                self.assertTrue("mode '%#o' out of range" % mode in str(e),
                                "mode: %#o" % mode)

        for mode in [0, 0o777]:
            oac_file.mode = mode
