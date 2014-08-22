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

"""Timeout decorator.

Source: http://stackoverflow.com/q/56011
The nose.tools.timed decorator is not good for our purposes because it only
checks if the time was exceeded after the function finishes, it doesn't
interrupt it.
"""

import functools
import errno
import os
import signal
import logging
import time
import datetime
import nose.tools

LOG = logging.getLogger(__name__)

# workaround: get rid of unnecessary log messages
logging.getLogger("iso8601").setLevel(logging.WARNING)


def timeout(seconds=10, error_message=os.strerror(errno.ETIME)):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise nose.tools.TimeExpired(error_message)

        def wrapper(*args, **kwargs):
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
            return result

        return functools.wraps(func)(wrapper)

    return decorator


def wait_for(label, condition, obj_getter, timeout_sec=120, period=1):
    """Wait for condition to be true until timeout.

    :param label: used for logging
    :param condition: function that takes the object from obj_getter and
        returns True or False
    :param obj_getter: function that returns the object on which the condition
        is tested
    :param timeout_sec: how many seconds to wait until a TimeoutError
    :param period: how many seconds to wait between testing the condition
    :raises: TimeoutError when timeout_sec is exceeded
             and condition isn't true
    """
    obj = obj_getter()
    timeout_ = datetime.timedelta(seconds=timeout_sec)
    start = datetime.datetime.now()
    LOG.info('%s - START' % label)
    while not condition(obj):
        if (datetime.datetime.now() - start) > timeout_:
            raise nose.tools.TimeExpired("waiting for '%s' expired after"
                                         " %d seconds"
                                         % (label, timeout_sec))
        time.sleep(period)
        obj = obj_getter()
    LOG.info('%s - DONE' % label)
    return obj
