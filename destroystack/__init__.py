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

import os.path
import destroystack.tools.common as common

def setUpPackage():
    if not os.path.exists(common.TESTFILE_DIR):
        os.makedirs(common.TESTFILE_DIR)
    # TODO generate config files from the main config file
	# TODO install swift on the server using packstack
	# TODO check setup sanity


def tearDownPackage():
    pass
	# TODO: remove swift, clean up the virtual disks
