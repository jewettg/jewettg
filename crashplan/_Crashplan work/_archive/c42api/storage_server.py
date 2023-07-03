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
A file to house the function, and the many functions it uses, that finds all
storage servers for either a list of plan uids or for every plan uid
associated with a single device guid.
"""

import itertools
import urlparse
import requests

from c42api.common import resources
from c42api.common.server import Server
from c42api.common.script_common import memoize
from c42api.common import logging_config

LOG = logging_config.get_logger(__name__)

def _fetch_storage_destinations(authority, plan_uid):
    """
    Fetches all storage destinations for a plan uid from the authority.

    :raise HTTPError: If the request fails
    :param authority: The Server object that points to the authority
    :param plan_uid:  The plan uid for the storage being requested
    :return:          A list of dictionaries that represent destinations
    """
    response = authority.json_from_response(authority.get([resources.STORAGE, plan_uid]))
    try:
        return response['data']
    except KeyError:
        return None


@memoize
def _fetch_all_destinations(authority):
    """
    Fetches all destinations from the authority.

    :raise HTTPError: If the request fails
    :param authority: The Server object that points to the authority
    :return:          A list of dictionaries that represent destinations
    """
    response = authority.json_from_response(authority.get(resources.DESTINATION))
    try:
        return response['data']['destinations']
    except KeyError:
        return None


@memoize
def _fetch_servers(authority, destination_id):
    """
    Fetches all servers associated with the destination id

    :raise HTTPError:      If the request fails
    :param authority:      The Server object that points to the authority
    :param destination_id: The destination id for the servers being requested
    :return:               A list of dictionaries that represent servers
    """
    params = {'destinationId': destination_id}
    response = authority.json_from_response(authority.get(resources.SERVER, params=params))
    try:
        return response['data']['servers']
    except KeyError:
        return None


def _request_auth_token(server, login_token):
    """
    If a login token has been granted, this fetches an auth token.

    :raise HTTPError:   If the request fails
    :param server:      The Server object to authorize against
    :param login_token: The one time use login token to use
    :return:            The auth token, or None if it failed
    """
    payload = {'sendCookieHeader': True}
    response = server.json_from_response(server.post(resources.AUTH_TOKEN, payload=payload, login_token=login_token))
    try:
        return "-".join(response['data'])
    except KeyError:
        return None


def _network_ping(node_url, **kwargs):
    """
    Sends a network ping request to a URL.

    :raise HTTPError: If the verification fails
    :param node_url:  The address address to be verified
    """
    ping_url = "{0}/api/ping".format(node_url)
    response = requests.get(ping_url, timeout=8, **kwargs)
    response.raise_for_status()


def _grouped_dict_by_key(list_of_dict, key):
    """
    Returns a dictionary of keys mapping to dictionaries that have that key as
    a value.

    :param list_of_dict: The list of dictionaries that needs to be grouped by
                          a common value on a specific key.
    :param key:          The key that it's grouping by.
    :return:             A dictionary of common values mapping to lists of
                          dictionaries that have that value.
    """
    result = {}
    groups = itertools.groupby(list_of_dict, key=lambda x: x[key])
    for key_out, group in groups:
        result[key_out] = list(group)
    return result


def _fetch_storage_servers(authority, plan_uid):
    """
    Fetches all viable storage servers for a plan uid.

    :param authority: The Server object that points to the authority
    :param plan_uid:  The plan uid to fetch the storage servers for
    :return:          A generator of Server objects
    """
    storage_destinations = _fetch_storage_destinations(authority, plan_uid)
    if not storage_destinations:
        yield None
    LOG.debug("Plan {0} has {1} storage destinations".format(plan_uid, len(storage_destinations)))
    for guid_key, storage_dict in storage_destinations.items():
        result = _server_object_for_destination(authority, plan_uid, guid_key, storage_dict)
        if result:
            LOG.debug("Found possible storage location for plan {0} at {1}".format(result, plan_uid))
            yield result


def _server_object_for_destination(authority, plan_uid, destination_guid, storage_dict):
    """
    Generates the appropriate auth'd Server objects for the supplied info.

    :param authority:        The Server object that points to the authority
    :param plan_uid:         The plan uid being requested
    :param destination_guid: The destination guid of the Server
    :param storage_dict:     A dictionary representing the storage server
    :return:                 An auth'd server object that is online
    """
    def url_and_storage_login_token():
        """
        Fetches a login token from the authority for a storage server

        :return: The url of the server and the login token
        """
        payload = {'planUid': str(plan_uid),
                   'destinationGuid': destination_guid}
        response = authority.json_from_response(authority.post(resources.STORAGE_AUTH_TOKEN, payload=payload))
        try:
            data = response['data']
            return urlparse.urlparse(data['serverUrl']), data['loginToken']
        except KeyError:
            return None, None

    def build_node_server():
        """
        Common code for building a provider or storage node server.

        :return: An auth'd server object
        """
        # if we failed to login/obtain auth token, return None so that we move onto the next
        # possible location
        try:
            url, login_token = url_and_storage_login_token()
            result_server = Server(url.hostname, url.port, protocol=url.scheme,
                                   verify_ssl=authority.verify_ssl)
            auth_token = _request_auth_token(result_server, login_token)
        except requests.HTTPError:
            LOG.debug("Failed to auth with location")
            return None

        result_server.authorization = auth_token
        return result_server

    LOG.debug("Attempting to auth with storage location (destination_guid:{0}, url:{1})".format(destination_guid, storage_dict['url']))

    node_url = storage_dict['url']
    try:
        # network test resource only wants hostname, no scheme or port
        LOG.debug("Determining reachability for server {0}".format(node_url))
        _network_ping(node_url, verify=authority.verify_ssl)
    except requests.HTTPError:
        # The server ping was not successful
        LOG.debug("Network ping determined location unreachable")
        return None

    destinations_by_guid = _grouped_dict_by_key(_fetch_all_destinations(authority), 'guid')
    target_destination = destinations_by_guid[destination_guid][0]
    if target_destination['type'] == 'PROVIDER':
        LOG.debug("Target location is a provider")
        return build_node_server()

    destination_id = target_destination['destinationId']
    servers_by_url = _grouped_dict_by_key(_fetch_servers(authority, destination_id), 'websiteHost')
    target_server = servers_by_url[node_url][0]
    if not target_server:
        LOG.debug("Cannot auth with location because unable to determine location type.")
        return None

    if target_server['type'] == 'STORAGE':
        LOG.debug("Target location is a storage node")
        return build_node_server()

    LOG.debug("Target location is the authority. We are already authenticated with it.")
    return authority


def storage_servers(authority, plan_uids=None, device_guid=None):
    """
    Returns a generator of destinations based on the input.

    Automatically handle's special logic for private storage nodes, private
    authorities, provider authorities and provider storage nodes. Loops over
    every potentially viable server and performs the following:

    # Overview

    1) Test if node is reachable, bail if not
    2) Check destination type by matching destination guid list of node's
       authority destinations

    - If destination is a provider:

        3) Send storage auth request to private authority for provider node
        4) Using serverUrl and login token from storage auth request, obtain
           auth token from provider node

    - Otherwise destination is a private authority or private storage node:

        3) Check destination id by matching destination guid list of node's
        authority destinations
        4) Using destination id, ask node's authority for servers at
           destination id
        5) Find server by matching the server's websiteHost param with node's
           url
        6) Look at server parameters to determine if is a storage server or
           authority

        - If is storage node (same as provider):
            7) Send storage auth request to private authority for storage node
            8) Using serverUrl and login token from storage auth request,
               obtain auth token from storage node


    9) Return result if successful, None if not

    :param authority:   The Server object that points to the authority
    :param plan_uids:   The optional list of plan uids
    :param device_guid: The optional device guid
    :return:            A generator of destinations that are all online
    """
    def fetch_plan_uids():
        """
        Fetches plan uids for the device guid, or just the ones passed in.

        :return: A list of plan uids
        """
        if plan_uids:
            return plan_uids
        params = {'sourceComputerGuid': device_guid,
                  'planTypes': 'BACKUP'}
        response = authority.get(resources.PLAN, params)
        response = authority.json_from_response(response)
        try:
            return [info['planUid'] for info in response['data']]
        except KeyError:
            return None

    LOG.debug("Fetching storage server(s) for device {0} and plans {1}".format(device_guid, plan_uids))
    plan_uids = fetch_plan_uids()
    for plan_uid in plan_uids:
        for possible_destination in _fetch_storage_servers(authority, plan_uid):
            yield possible_destination, plan_uid
