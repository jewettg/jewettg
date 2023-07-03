# Copyright (c) 2015 - 2016 Code42 Software, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
A module for fetching every user on a Code42 installation. All it takes is a
Server object that points to a Code42 server.
"""

from datetime import datetime

from c42api.common.server import Server
from c42api.common import resources
from c42api.common import logging_config
from c42api.common import analytics

SCHEMA_VERSION = 1
LOG = logging_config.get_logger(__name__)


@analytics.with_lock
def log_analytics(**kwargs):
    """
    Passes on anything to be logged for analytics.
    """
    analytics.write_json_analytics(__name__, kwargs, result_limit=1)


def fetch_users(server):
    """
    Returns an iterable (specifically a generator) containing json objects
    that represent users.

    :param server: A Server object to make the API call to
    """
    start_time = datetime.now().isoformat()
    user_count = 0

    LOG.info('Fetching user info from %s.', server.server_address)
    params = {'pgSize': str(Server.MAX_PAGE_SIZE),
              'active': 'true',
              'incRoles': 'true'}
    results = server.fetch_all_paged(resources.USER, params, 'users')
    for user in results:
        user['schema_version'] = SCHEMA_VERSION
        user_count += 1
        yield user
    LOG.info('Done fetching user info.')

    end_time = datetime.now().isoformat()
    log_analytics(start_time=start_time,
                  end_time=end_time,
                  user_count=user_count)
