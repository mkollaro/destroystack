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

from exceptions import AssertionError
import logging
import destroystack.tools.common as common
import destroystack.tools.servers as server_tools

LOG = logging.getLogger(__name__)
TIMEOUT = common.get_timeout()


def run(include=None, exclude=None, test_type=None, test_dir="api",
        regexp=None, concurrency=4):
    """Run part of Tempest using tox.

    This function expects that Tempest is already configured in the directory
    given in the configuration file under "tempest_dir".

    TODO: parse result, return number of test ran/succeeded/failed

    :param include: which tests should run (e.g. 'identity', 'compute', ..)
    :param exclude: which tests to skip, (TODO: not implemented)
    :param test_type: can be "smoke" or "gate" or other test types
    :param test_dir: which directory in tempest/ to search for the tests
    :param regexp: specify your own regular expression to filter tests, this
        will overwrite the parameters `include`, `exclude`, `test_type`,
        and `test_dir`
    :param concurrency: how many threads to use to execute the tests

    :returns: `tools.servers.CommandResult` of the test run
    :raises: AssertionError if one of the tests fail
    """
    if exclude:
        raise NotImplementedError("The `exclude` param is not implemented")
    tempest_dir = common.CONFIG.get("tempest", None)
    if not tempest_dir:
        raise Exception("Tempest directory not provided in config")

    if not regexp:
        regexp = "(^tempest\.%s\.%s.*%s.*)" % (test_dir, include, test_type)
    cmd = ("cd %s && tox -eall '%s' --"
           " --concurrency=%s" % (tempest_dir, regexp, concurrency))

    localhost = server_tools.LocalServer()
    result = localhost.cmd(cmd, ignore_failures=True)
    if result.exit_code == 0:
        return result
    else:
        raise AssertionError("Some of the Tempest tests failed, system is not"
                             " functional")
