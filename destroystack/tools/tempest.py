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

import logging
import destroystack.tools.common as common

LOG = logging.getLogger(__name__)
TIMEOUT = common.get_timeout()


class Tempest(object):
    def __init__(self, tempest_dir):
        self._dir = tempest_dir

    def run(self, include=None, exclude=None, test_type=None):
        pass