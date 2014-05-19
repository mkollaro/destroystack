#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#           http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import json
import random
import string
import logging
from optparse import OptionParser

PROJ_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
PROJ_DIR = os.path.normpath(PROJ_DIR)
CONFIG_DIR = os.path.join(PROJ_DIR, "etc")
BIN_DIR = os.path.join(PROJ_DIR, "bin")
TESTFILE_DIR = os.path.join(PROJ_DIR, "tmp", "test_files")

SUPPORTED_SETUPS = ["swift_small_setup"]
# file in the ./etc/ direcotry
MAIN_CONFIG_FILE = os.environ.get("MAIN_CONFIG_FILE", "config.json")

LOG = logging.getLogger(__name__)


class ConfigException(Exception):
    pass


def get_config(filename=MAIN_CONFIG_FILE):
    """Load dict from a JSON configuration file in CONF_DIR."""
    with open(os.path.join(CONFIG_DIR, filename)) as f:
        config = json.load(f)
    return config


def get_timeout():
    """Get the timeout configuration from etc/config.json"""
    return get_config()["timeout"]


def get_keystone_auth():
    """Get the keystone authentication info from the configuration file.

    The auth_url for keystone will be found out from the servers (it will
    search for a server that has the 'keystone' role). If the keystone username
    is not provided, it will be 'admin'. If the tenant is not provided, it will
    be the same as the user name. The password is required in the
    configuration.

    :returns: (auth_url, user, tenant, password)
    """
    config = get_config()
    user = config['keystone'].get('user', 'admin')
    tenant = config['keystone'].get('tenant', user)
    password = config['keystone']['password']

    # find out the auth_url
    keystone_server = None
    for server in config['servers']:
        if 'roles' in server and 'keystone' in server['roles']:
            keystone_server = server
    if not keystone_server:
        raise Exception("No server with 'keystone' role found")
    host = keystone_server.get('hostname', None)
    if not host:
        host = keystone_server['ip']
    auth_url = 'http://%s:5000/v2.0/' % host
    return (auth_url, user, tenant, password)


def get_option_parser():
    parser = OptionParser()
    parser.add_option("-s", "--setup", dest="setup",
                      help="Which OpenStack setup to deploy. "
                           "Supported are: %s" % SUPPORTED_SETUPS)
    return parser


def upload_files(swift, container, filename_list):
    """Upload files from the TESTFILE_DIR.

    Creates the container if it doesn't exist.
    """
    swift.put_container(container)
    for filename in filename_list:
        f = open(os.path.join(TESTFILE_DIR, filename))
        swift.put_object(container, filename, f)


def populate_swift_with_random_files(swift, prefix='',
                                     container_count=5, files_per_container=5):
    """ Create random files in test_files dir and upload them to Swift.

    :param prefix: prefix before container and file names
    :param container_count: how many containers to create
    :param files_per_container: how many files to upload per container
    """
    LOG.info("Uploading random files to Swift")
    containers = [prefix + "container" + str(i)
                  for i in range(0, container_count)]
    files = [prefix + "file" + str(i) + ".txt"
             for i in range(0, container_count*files_per_container)]
    if not os.path.exists(TESTFILE_DIR):
        os.makedirs(TESTFILE_DIR)
    for filename in files:
        f = open(os.path.join(TESTFILE_DIR, filename), 'w')
        f.write(random_string()+'\n')
        f.close()
    start = 0
    for container in containers:
        upload_files(swift, container, files[start:start+files_per_container])
        start += files_per_container
    LOG.info("Finished uploading random files to Swift")


def delete_testfiles(prefix=''):
    """ Delete all *.txt file in test_files directory

    :param prefix: only delete files starting with prefix
    """
    os.chdir(TESTFILE_DIR)
    for f in os.listdir("."):
        if f.endswith(".txt") and f.startswith(prefix):
            os.remove(f)


def random_string(min_lenght=1, max_length=20):
    """ Generate random string made out of alphanumeric characters. """
    length = random.randint(min_lenght, max_length)
    chars = string.ascii_letters + string.digits

    return ''.join([random.choice(chars) for _ in range(length)])


def represents_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False
