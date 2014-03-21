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
LOG = logging.getLogger(__name__)


def save(configuration, tag=''):
    #if configuration['management']['type'] == 'openstack'
    name = _get_snapshot_name(configuration, tag)
    LOG.info("Creating snapshot '%s'" % name)


def load(configuration, tag=''):
    name = _get_snapshot_name(configuration, tag)
    LOG.info("Loading snapshot '%s'" % name)


def _get_snapshot_name(configuration, tag):
    #basename = configuration['management']['snapshot_prefix']
    basename = 'destroystack'
    name = '-'.join([basename, 'snapshot', tag])
    return name
