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

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile

from pystache import context
import yaml

from os_apply_config import collect_config
from os_apply_config import config_exception as exc
from os_apply_config import oac_file
from os_apply_config import renderers
from os_apply_config import value_types
from os_apply_config import version

DEFAULT_TEMPLATES_DIR = '/usr/libexec/os-apply-config/templates'


def templates_dir():
    """Determine the default templates directory path

    If the OS_CONFIG_APPLIER_TEMPLATES environment variable has been set,
    use its value.
    Otherwise, select a default path based on which directories exist on the
    system, preferring the newer paths but still allowing the old ones for
    backwards compatibility.
    """
    templates_dir = os.environ.get('OS_CONFIG_APPLIER_TEMPLATES', None)
    if templates_dir is None:
        templates_dir = '/opt/stack/os-apply-config/templates'
        if not os.path.isdir(templates_dir):
            # Backwards compat with the old name.
            templates_dir = '/opt/stack/os-config-applier/templates'
        if (os.path.isdir(templates_dir) and
                not os.path.isdir(DEFAULT_TEMPLATES_DIR)):
            logging.warning('Template directory %s is deprecated.  The '
                            'recommended location for template files is %s',
                            templates_dir, DEFAULT_TEMPLATES_DIR)
        else:
            templates_dir = DEFAULT_TEMPLATES_DIR
    return templates_dir


TEMPLATES_DIR = templates_dir()
OS_CONFIG_FILES_PATH = os.environ.get(
    'OS_CONFIG_FILES_PATH', '/var/lib/os-collect-config/os_config_files.json')
OS_CONFIG_FILES_PATH_OLD = '/var/run/os-collect-config/os_config_files.json'

CONTROL_FILE_SUFFIX = ".oac"


def install_config(
        config_path, template_root, output_path, validate, subhash=None,
        fallback_metadata=None):
    config = strip_hash(
        collect_config.collect_config(config_path, fallback_metadata), subhash)
    tree = build_tree(template_paths(template_root), config)
    if not validate:
        for path, obj in tree.items():
            write_file(os.path.join(
                output_path, strip_prefix('/', path)), obj)


def _extract_key(config_path, key, fallback_metadata=None):
    config = collect_config.collect_config(config_path, fallback_metadata)
    keys = key.split('.')
    for key in keys:
        try:
            config = config[key]
            if config is None:
                raise TypeError()
        except (KeyError, TypeError):
            try:
                if type(config) == list:
                    config = config[int(key)]
                    continue
            except (IndexError, ValueError):
                pass
            return None
    return config


def print_key(
        config_path, key, type_name, default=None, fallback_metadata=None):
    config = collect_config.collect_config(config_path, fallback_metadata)
    config = _extract_key(config_path, key, fallback_metadata)
    if config is None:
        if default is not None:
            print(str(default))
            return
        else:
            raise exc.ConfigException(
                'key %s does not exist in %s' % (key, config_path))
    value_types.ensure_type(str(config), type_name)
    if isinstance(config, (dict, list, bool)):
        print(json.dumps(config))
    else:
        print(str(config))


def boolean_key(metadata, key, fallback_metadata):
    config = _extract_key(metadata, key, fallback_metadata)
    if not isinstance(config, bool):
        return -1
    if config:
        return 0
    else:
        return 1


def write_file(path, obj):
    if not obj.allow_empty and len(obj.body) == 0:
        if os.path.exists(path):
            logger.info("deleting %s", path)
            os.unlink(path)
        else:
            logger.info("not creating empty %s", path)
        return

    logger.info("writing %s", path)
    if os.path.exists(path):
        stat = os.stat(path)
        mode, uid, gid = stat.st_mode, stat.st_uid, stat.st_gid
    else:
        mode, uid, gid = 0o644, -1, -1
    mode = obj.mode or mode
    if obj.owner is not None:
        uid = obj.owner
    if obj.group is not None:
        gid = obj.group

    d = os.path.dirname(path)
    os.path.exists(d) or os.makedirs(d)
    with tempfile.NamedTemporaryFile(dir=d, delete=False) as newfile:
        if type(obj.body) == str:
            obj.body = obj.body.encode('utf-8')
        newfile.write(obj.body)
        os.chmod(newfile.name, mode)
        os.chown(newfile.name, uid, gid)
        os.rename(newfile.name, path)


def build_tree(templates, config):
    """Return a map of filenames to OacFiles."""
    res = {}
    for in_file, out_file in templates:
        try:
            body = render_template(in_file, config)
            ctrl_file = in_file + CONTROL_FILE_SUFFIX
            ctrl_dict = {}
            if os.path.isfile(ctrl_file):
                with open(ctrl_file) as cf:
                    ctrl_body = cf.read()
                ctrl_dict = yaml.safe_load(ctrl_body) or {}
            if not isinstance(ctrl_dict, dict):
                raise exc.ConfigException(
                    "header is not a dict: %s" % in_file)
            res[out_file] = oac_file.OacFile(body, **ctrl_dict)
        except exc.ConfigException as e:
            e.args += in_file,
            raise
    return res


def render_template(template, config):
    if is_executable(template):
        return render_executable(template, config)
    else:
        try:
            return render_moustache(open(template).read(), config)
        except context.KeyNotFoundError as e:
            raise exc.ConfigException(
                "key '%s' from template '%s' does not exist in metadata file."
                % (e.key, template))
        except Exception as e:
            logger.error("%s", e)
            raise exc.ConfigException(
                "could not render moustache template %s" % template)


def is_executable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def render_moustache(text, config):
    r = renderers.JsonRenderer(missing_tags='ignore')
    return r.render(text, config)


def render_executable(path, config):
    p = subprocess.Popen([path],
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(json.dumps(config).encode('utf-8'))
    p.wait()
    if p.returncode != 0:
        raise exc.ConfigException(
            "config script failed: %s\n\nwith output:\n\n%s" %
            (path, stdout + stderr))
    return stdout.decode('utf-8')


def template_paths(root):
    res = []
    for cur_root, _subdirs, files in os.walk(root):
        for f in files:
            if f.endswith(CONTROL_FILE_SUFFIX):
                continue
            inout = (os.path.join(cur_root, f), os.path.join(
                strip_prefix(root, cur_root), f))
            res.append(inout)
    return res


def strip_prefix(prefix, s):
    return s[len(prefix):] if s.startswith(prefix) else s


def strip_hash(h, keys):
    if not keys:
        return h
    for k in keys.split('.'):
        if k in h and isinstance(h[k], dict):
            h = h[k]
        else:
            raise exc.ConfigException(
                "key '%s' does not correspond to a hash in the metadata file"
                % keys)
    return h


def parse_opts(argv):
    parser = argparse.ArgumentParser(
        description='Reads and merges JSON configuration files specified'
        ' by colon separated environment variable OS_CONFIG_FILES, unless'
        ' overridden by command line option --metadata. If no files are'
        ' specified this way, falls back to legacy behavior of searching'
        ' the fallback metadata path for a single config file.')
    parser.add_argument('-t', '--templates', metavar='TEMPLATE_ROOT',
                        help="""path to template root directory (default:
                        %(default)s)""",
                        default=TEMPLATES_DIR)
    parser.add_argument('-o', '--output', metavar='OUT_DIR',
                        help='root directory for output (default:%(default)s)',
                        default='/')
    parser.add_argument('-m', '--metadata', metavar='METADATA_FILE', nargs='*',
                        help='Overrides environment variable OS_CONFIG_FILES.'
                        ' Specify multiple times, rather than separate files'
                        ' with ":".',
                        default=[])
    parser.add_argument('--fallback-metadata', metavar='FALLBACK_METADATA',
                        nargs='*', help='Files to search when OS_CONFIG_FILES'
                        ' is empty. (default: %(default)s)',
                        default=['/var/cache/heat-cfntools/last_metadata',
                                 '/var/lib/heat-cfntools/cfn-init-data',
                                 '/var/lib/cloud/data/cfn-init-data'])
    parser.add_argument(
        '-v', '--validate', help='validate only. do not write files',
        default=False, action='store_true')
    parser.add_argument(
        '--print-templates', default=False, action='store_true',
        help='Print templates root and exit.')
    parser.add_argument('-s', '--subhash',
                        help='use the sub-hash named by this key,'
                             ' instead of the full metadata hash')
    parser.add_argument('--key', metavar='KEY', default=None,
                        help='print the specified key and exit.'
                             ' (may be used with --type and --key-default)')
    parser.add_argument('--type', default='default',
                        help='exit with error if the specified --key does not'
                             ' match type. Valid types are'
                             ' <int|default|netaddress|netdevice|dsn|'
                             'swiftdevices|raw>')
    parser.add_argument('--key-default',
                        help='This option only affects running with --key.'
                             ' Print this if key is not found. This value is'
                             ' not subject to type restrictions. If --key is'
                             ' specified and no default is specified, program'
                             ' exits with an error on missing key.')
    parser.add_argument('--boolean-key',
                        help='This option is incompatible with --key.'
                             ' Use this to evaluate whether a value is'
                             ' boolean true or false. The return code of the'
                             ' command will be 0 for true, 1 for false, and -1'
                             ' for non-boolean values.')
    parser.add_argument('--version', action='version',
                        version=version.version_info.version_string())
    parser.add_argument('--os-config-files',
                        default=OS_CONFIG_FILES_PATH,
                        help='Set path to os_config_files.json')
    opts = parser.parse_args(argv[1:])

    return opts


def load_list_from_json(json_file):
    json_obj = []
    if os.path.exists(json_file):
        with open(json_file) as ocf:
            json_obj = json.loads(ocf.read())
    if not isinstance(json_obj, list):
        raise ValueError("No list defined in json file: %s" % json_file)
    return json_obj


def main(argv=sys.argv):
    opts = parse_opts(argv)
    if opts.print_templates:
        print(opts.templates)
        return 0

    if not opts.metadata:
        if 'OS_CONFIG_FILES' in os.environ:
            opts.metadata = os.environ['OS_CONFIG_FILES'].split(':')
        else:
            opts.metadata = load_list_from_json(opts.os_config_files)
            if ((not opts.metadata and opts.os_config_files ==
                 OS_CONFIG_FILES_PATH)):
                logger.warning('DEPRECATED: falling back to %s' %
                               OS_CONFIG_FILES_PATH_OLD)
                opts.metadata = load_list_from_json(OS_CONFIG_FILES_PATH_OLD)

    if opts.key and opts.boolean_key:
        logger.warning('--key is not compatible with --boolean-key.'
                       ' --boolean-key ignored.')

    try:
        if opts.templates is None:
            raise exc.ConfigException('missing option --templates')

        if opts.key:
            print_key(opts.metadata,
                      opts.key,
                      opts.type,
                      opts.key_default,
                      opts.fallback_metadata)
        elif opts.boolean_key:
            return boolean_key(opts.metadata,
                               opts.boolean_key,
                               opts.fallback_metadata)
        else:
            install_config(opts.metadata, opts.templates, opts.output,
                           opts.validate, opts.subhash, opts.fallback_metadata)
            logger.info("success")
    except exc.ConfigException as e:
        logger.error(e)
        return 1
    return 0


# logging
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s'
DATE_FORMAT = '%Y/%m/%d %I:%M:%S %p'


def add_handler(logger, handler):
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
logger = logging.getLogger('os-apply-config')
logger.setLevel(logging.INFO)
add_handler(logger, logging.StreamHandler())
if os.geteuid() == 0:
    add_handler(logger, logging.FileHandler('/var/log/os-apply-config.log'))

if __name__ == '__main__':
    sys.exit(main(sys.argv))
