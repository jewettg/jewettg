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
A script for fetching security detection events
"""

# pylint: disable=import-error

import re
import copy
from Queue import Queue
from datetime import datetime

from c42api.common.thread_pool import ThreadPool
from c42api.common.atomic_counter import AtomicCounter
from c42api.common import resources
from c42api.common import logging_config
import c42api.storage_server as fetch_storage
from c42api.common import analytics
from requests import HTTPError

LOG = logging_config.get_logger(__name__)
SCHEMA_VERSION = 1
NUM_THREADS = 4


@analytics.with_lock
def log_analytics(**kwargs):
    """
    Passes on anything to be logged for analytics.
    """
    analytics.write_json_analytics(__name__, kwargs, result_limit=10)


def _fetch_detection_events(server, plan_uid, event_filter):
    """
    Fetch security detection events for a given plan_uid

    :raise                  HTTPError: If the request fails
    :param server:          The Server object
    :param plan_uid:        Plan to get detection events from
    :param event_filter:    Filter to use when downloading events
    :return:                returns a tuple of the cursor string and the list of
                             detection events -> (cursor_string, detection_events)
    """
    assert ('minTs' in event_filter and 'maxTs' in event_filter) or 'cursor' in event_filter
    params = event_filter
    params['planUid'] = plan_uid
    params['incFiles'] = True
    response = server.json_from_response(server.get(resources.SECURITY_DETECTION_EVENTS, params=params))
    try:
        return response['data']['cursor'], response['data']['securityDetectionEvents']
    except KeyError:
        return None, None


def _fetch_security_plan(server, device_guid):
    """
    Get plan with planType == 'SECURITY' for a device.
    Should only be one per device

    :raise              HTTPError: If the request fails
    :param server:      The Server object
    :param device_guid: Device to get plan for
    :return:            A single plan
    """

    params = {'sourceComputerGuid': device_guid}
    response = server.json_from_response(server.get(resources.PLAN, params=params))
    try:
        plans = [x for x in response['data'] if x['planType'].lower() == 'security']
        if len(plans) > 1:
            LOG.warn("Device %d had more than 1 security plan. Returning first one", device_guid)
        return plans[0]
    except (KeyError, IndexError):
        return None


def _append_schema_version(detection_event):
    """
    Read the function name
    """
    detection_event['schema_version'] = SCHEMA_VERSION

def _unbatch_files_in_events(detection_events):
    """
    Convert a list of batched detection events into a list of single-file
    detection events.

    Detection events can be batched, wherein a single event (for example,
    a PERSONAL_CLOUD_FILE_ACTIVITY event) may have an array of multiple file
    dictionaries. We do not want this structure when sending the events to
    another program or directly to a user. Hence, we will send individual
    events for each file.

    :param detection_events: A list of detection event dictionaries that may
                              or may not have a files list in them.
    :return:                 A list of detection events each containing
                              information about at most one file. (There may
                              be no file information.)
    """
    unbatched_events = []
    for detection_event in detection_events:
        try:
            files_list = detection_event["files"]
            for file_dict in files_list:
                unbatched_event = copy.deepcopy(detection_event)
                del unbatched_event["files"]
                del unbatched_event["fileStats"]
                unbatched_event["file"] = file_dict
                unbatched_event["timestamp"] = file_dict["detectionTimestamp"]
                unbatched_events.append(unbatched_event)
        except (KeyError, TypeError):
            unbatched_events.append(detection_event)
    return unbatched_events

# pylint: disable=invalid-name
def _fetch_detection_events_for_device(authority, device_guid, detection_event_filter):
    """
    Returns detections events and the corresponding cursor string for the target device

    :param authority:               A Server object to make the API call to
    :param device_guid:             Device to retrieve events for
    :param detection_event_filter:  Filter to use when pulling detection events
    :return:                        returns a tuple of the cursor string and the list of
                                     detection events -> (cursor_string, detection_events)
    """
    security_plan = _fetch_security_plan(authority, device_guid)
    if not security_plan:
        LOG.debug("No security plan found for device: %s", str(device_guid))
        return None, []
    LOG.debug("Found security plan")
    for storage_server, plan_uid in fetch_storage.storage_servers(authority, [security_plan['planUid']], device_guid):
        updated_cursor, detection_events = _fetch_detection_events(storage_server, plan_uid,
                                                                   detection_event_filter)
        if updated_cursor and detection_events:
            for detection_event in detection_events:
                _append_schema_version(detection_event)

            return updated_cursor, _unbatch_files_in_events(detection_events)
    return None, []


def create_filter_by_utc_datetime(min_datetime, max_datetime):
    """
    Create a minTs, maxTs filter. Datetime object must be in utc time. API contract requires it.
    """

    if min_datetime > max_datetime:
        raise ValueError("min_datetime > max_datetime")

    try:
        # Basic Datetime object does not create the correctly formatted timestamp
        # necessary when making SecurityDetectionEvents API calls. That is why we
        # have the custum time formatter.
        return {'minTs': min_datetime.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                'maxTs': max_datetime.strftime("%Y-%m-%dT%H:%M:%S.000Z")}
    except ValueError:
        LOG.error("Failed to create event_filter")
        return None


def create_filter_by_cursor(cursor):
    """
    Create a cursor filter
    """
    # cursor is two positives longs, plan_uid and event_uid, seperated by a colon
    if not re.match("(^[0-9]{1,19}:[0-9]{1,19}$)", cursor):
        raise ValueError("Invalid cursor format")

    return {'cursor': cursor}


def fetch_detection_events(authority, guid_and_filter_list):
    """
    Returns an iterable (specifically a generator) containing json objects
    that represent security detection events for a specific device guid.

    :param authority:            A Server object to make the API call to
    :param guid_and_filter_list: A pre-zipped list of (device_guid,
                                  event_filter)
    :return:                     returns a tuple of the device_guid, the cursor
                                  string and a list of detection events
                                  (device_guid, cursor, detection events)
    """
    start_time = datetime.now().isoformat()
    event_count = 0
    device_guids = [item[0] for item in guid_and_filter_list]
    LOG.info("Begin fetching detection events devices:%s", str(device_guids))
    pool = ThreadPool(NUM_THREADS)
    counter = AtomicCounter(len(device_guids))
    result_queue = Queue()

    def thread_fetch_detection_events(guid, event_filter):
        """
        Per thread logic. Get detection events for device guid and add to
        list of all detection events

        The _fetch_detection_events_for_device() call could return nothing but our exit condition
        expects that every task will return some result so no matter what, we have to output
        a result to the result_queue.
        """
        LOG.debug("Fetching detection events for %s", str(guid))
        cursor = None
        detection_events = []
        try:
            cursor, detection_events = _fetch_detection_events_for_device(authority, guid, event_filter)
            LOG.info("Got %d detection events", len(detection_events) if detection_events else 0)
        except HTTPError:
            LOG.exception("Failure when fetching detection events for device %s", str(guid))

        result_queue.put((guid, cursor, detection_events))
        counter.decrement()

    for device_guid, detection_event_filter in guid_and_filter_list:
        pool.add_task(thread_fetch_detection_events, device_guid, detection_event_filter)

    while not result_queue.empty() or counter.get() > 0:
        results = result_queue.get()
        event_count += len(results[2])
        yield results

    pool.wait_completion()
    LOG.info("Finished fetching detection events for devices %s", str(device_guids))
    end_time = datetime.now().isoformat()
    log_analytics(start_time=start_time,
                  end_time=end_time,
                  event_count=event_count)
