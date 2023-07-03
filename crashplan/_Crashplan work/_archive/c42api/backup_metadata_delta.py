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
Calculate a backup selection metadata delta between two dates for a computer.

Using ArchiveMetadata (API), calculate the changes that have happened for a device
backup over a time range, such as files created or modified (new versions created),
and files deleted (empty file version).

**************************************************************************************
*** THIS SCRIPT DOES NOT PERFORM AT SCALE, AND CAN ONLY BE RUN FOR A SINGLE DEVICE ***
**************************************************************************************
"""

from dateutil import parser
from datetime import datetime

import c42api.storage_server as fetch_storage
from c42api.common import logging_config
from c42api.common import resources
from c42api.common import analytics

SCHEMA_VERSION = 1
DELETED_CHECKSUM = 'ffffffffffffffffffffffffffffffff'

LOG = logging_config.get_logger(__name__)


@analytics.with_lock
def log_analytics(**kwargs):
    """
    Passes on anything to be logged for analytics.
    """
    analytics.write_json_analytics(__name__, kwargs, size_limit=1024 * 1024)


def unicode_str_replace(string):
    """
    Strip all special unicode characters from a string.
    """
    return string.replace("\\", "\\\\").encode('ascii', 'ignore').decode('unicode_escape')


def calculate_delta(server, device_guid, min_date, max_date, include_dirs=True):
    """
    Calculate a backup selection metadata delta between two dates for a computer.

    Using ArchiveMetadata (API), calculate the changes that have happened for a device
    backup over a time range, such as files created or modified (new versions created),
    and files deleted (empty file version).

    Args:
        device_guid (str):       Device GUID for delta calculation.
        minimum_date (datetime): Date for the base during delta calculation.
        maximum_date (datetime): Date for the opposing delta calculation.
        include_folders (bool):  Whether folders should be included in results.
        server (Server):         Master server containing device backup routing information.

    Returns:
        list: List of all file version events as objects.
    """

    def file_version_filter(version):
        """
        Determines whether a file version is included in the current query.

        :param version: The file version to filter.
        :return:        Whether or not it's included in the current query.
        """
        if not include_dirs and version['fileType'] == 1:
            return False
        # pylint: disable=no-member
        version_timestamp = parser.parse(version['versionTimestamp']).replace(tzinfo=None)
        return min_date < version_timestamp < max_date

    def fetch_data_key_token():
        """
        Fetches the data key token from the authority.

        :return: The data key token, or None
        """
        payload = {'computerGuid': device_guid}
        response = server.json_from_response(server.post(resources.DATA_KEY_TOKEN, payload=payload))
        try:
            return response['data']['dataKeyToken']
        except KeyError:
            return None

    def event_from_version(version):
        """
        Translates a version to an event dictionary.

        :param version: The version to translate
        :return:        The translated event
        """
        file_dict = {'fullPath': unicode_str_replace(version['path']),
                     'fileName': unicode_str_replace(version['path'].split('/')[-1]),
                     'length': int(version['sourceLength']),
                     'MD5Hash': unicode_str_replace(version['sourceChecksum']),
                     'lastModified': int(version['timestamp']),
                     'fileType': int(version['fileType'])}
        event = {'deviceGuid': int(device_guid),
                 'timestamp': int(version['timestamp']),
                 'schema_version': SCHEMA_VERSION,
                 'files': [file_dict]}
        if 'checksum' in version and version['checksum'] == DELETED_CHECKSUM:
            event['eventType'] = 'BACKUP_FILE_DELETED'
            file_dict['fileEventType'] = 'delete'
            file_dict['MD5Hash'] = ''
            file_dict['length'] = 0
        else:
            event['eventType'] = 'BACKUP_FILE_ACTIVITY'
            file_dict['fileEventType'] = 'activity'

        if version['fileType'] == 1:
            # CrashPlan keeps some inaccurate data about folders we want to remove.
            file_dict['MD5Hash'] = ''
            file_dict['length'] = 0
        return event

    def run():
        """
        Runs the logic and yields events.
        """
        start_time = datetime.now().isoformat()
        storage_server_count = 0
        total_file_version_count = 0
        used_file_version_count = 0

        for storage_server, _ in fetch_storage.storage_servers(server, device_guid=device_guid):
            storage_server_count += 1
            data_key_token = fetch_data_key_token()
            params = {'idType': 'guid',
                      'decryptPaths': 'true',
                      'dataKeyToken': data_key_token}
            response = storage_server.get([resources.ARCHIVE_METADATA, device_guid], params)
            response = server.json_from_response(response)
            versions = sorted(response['data'], key=lambda x: (x['path'], x['versionTimestamp']))
            for version in versions:
                total_file_version_count += 0
                if file_version_filter(version):
                    used_file_version_count += 0
                    yield event_from_version(version)

            # After we go to one storage node, we should be done calculating
            # the delta, otherwise duplicates will occur.
            break

        end_time = datetime.now().isoformat()
        log_analytics(start_time=start_time,
                      end_time=end_time,
                      storage_server_count=storage_server_count,
                      total_file_version_count=total_file_version_count,
                      used_file_version_count=total_file_version_count)

    return run()
