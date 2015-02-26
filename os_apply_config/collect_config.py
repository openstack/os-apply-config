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

import copy
import json
import os

from os_apply_config import config_exception as exc


def read_configs(config_files):
    '''Generator yields data from any existing file in list config_files.'''
    for input_path in [x for x in config_files if x]:
        if os.path.exists(input_path):
            try:
                with open(input_path) as input_file:
                    yield((input_file.read(), input_path))
            except IOError as e:
                raise exc.ConfigException('Could not open %s for reading. %s' %
                                          (input_path, e))


def parse_configs(config_data):
    '''Generator yields parsed json for each item passed in config_data.'''
    for input_data, input_path in config_data:
        try:
            yield(json.loads(input_data))
        except ValueError:
            raise exc.ConfigException('Could not parse metadata file: %s' %
                                      input_path)


def _deep_merge_dict(a, b):
    if not isinstance(b, dict):
        return b
    new_dict = copy.deepcopy(a)
    for k, v in iter(b.items()):
        if k in new_dict and isinstance(new_dict[k], dict):
            new_dict[k] = _deep_merge_dict(new_dict[k], v)
        else:
            new_dict[k] = copy.deepcopy(v)
    return new_dict


def merge_configs(parsed_configs):
    '''Returns deep-merged dict from passed list of dicts.'''
    final_conf = {}
    for conf in parsed_configs:
        if conf:
            final_conf = _deep_merge_dict(final_conf, conf)
    return final_conf


def collect_config(os_config_files, fallback_paths=None):
    '''Convenience method to read, parse, and merge all paths.'''
    if fallback_paths:
        os_config_files = fallback_paths + os_config_files
    return merge_configs(parse_configs(read_configs(os_config_files)))
