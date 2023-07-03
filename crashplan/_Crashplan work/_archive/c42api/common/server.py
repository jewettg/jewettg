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
A file for a class that represents a server object and rest client. Run it to
run its tests.
"""

import requests
import base64
import json
import functools
from datetime import datetime
from c42api.common import logging_config
from c42api.common import analytics

LOG = logging_config.get_logger(__name__)


# decorator
def monitor_network(func):
    """
    Decorator that gets the size of the returned response object

    :param func: A function that returns an http response
    :return:     The wrapped function
    """

    @functools.wraps(func)
    @analytics.with_lock
    def wrapper_func(*args, **kwargs):
        """
        The wrapper function that grabs analytics from REST calls
        """
        analytic = kwargs.copy()
        analytic['start_time'] = datetime.now().isoformat()
        result = func(*args, **kwargs)
        analytic['end_time'] = datetime.now().isoformat()

        analytic['response_size'] = len(result.content)
        analytic['func_call'] = func.__name__
        analytic['resource'] = list(args)[1:]
        analytics.write_json_analytics('network', analytic, size_limit=1024 * 1024)

        return result

    return wrapper_func


class Server(object):
    """
    Class representing a server object and a REST client. Once instantiated it
    can be used to make REST requests. If there are multiple servers being
    used the existence of this class allows for an easy way to maintain
    differing pieces of information between them.

    This class is immutable. Do not even try to mutate it.
    """
    MAX_PAGE_SIZE = 250

    # pylint: disable=too-many-arguments
    def __init__(self, server_address, port=None, username=None, password=None, protocol=None, authorization=None,
                 verify_ssl=True):
        """
        :param server_address: The address of the server
                                (ex. code42.com -or- 10.10.32.128)
        :param port:           The port any requests will hit on the server
        :param username:       The username used to authenticate
        :param password:       The password for that username
        :param protocol:       Either http or https, default is to calculate this
                                 based on port & server_address fields.
        """
        server_address = server_address.rstrip('/')
        try:
            port = int(port)
        except (TypeError, ValueError):
            port = None

        self._server_address = server_address
        self._port = port
        self._protocol = protocol
        if (server_address.count(':') >= 2 or
                server_address.startswith('https:') or
                server_address.startswith('http:')):

            components = server_address.split(':')
            self._server_address = components[1][2:]
            if not protocol:
                self._protocol = components[0]
            if not port and len(components) >= 3:
                try:
                    self._port = int(components[2])
                except ValueError:
                    pass
        else:
            if not port:
                components = server_address.split(':')
                self._server_address = components[0]
                if len(components) >= 2:
                    try:
                        self._port = int(components[1])
                    except ValueError:
                        pass
                elif not protocol:
                    # Assume we should use HTTPS when using port-forwarding.
                    self._protocol = "https"

            if self._port and not protocol:
                if self._port in [443, 4285, 7285]:
                    self._protocol = "https"
                else:
                    self._protocol = "http"

        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self.authorization = authorization

    @property
    def server_address(self):
        """Getter for the immutable server_address"""
        return self._server_address

    @property
    def port(self):
        """Getter for the immutable port"""
        return self._port

    @property
    def verify_ssl(self):
        """Getter for the immutable verify_ssl"""
        return self._verify_ssl

    @property
    def username(self):
        """Getter for the immutable username"""
        return self._username

    @property
    def password(self):
        """Getter for the immutable password"""
        return self._password

    @password.setter
    def password(self, value):
        """Setter for the immutable password property"""
        if self._password:
            raise AttributeError("Server's password property cannot be set more than once.")
        self._password = value

    @property
    def protocol(self):
        """Getter for the immutable protocol"""
        return self._protocol

    def _get_auth_header(self, login_token):
        """Authentication header generation"""
        if login_token:
            return {'Authorization': "LOGIN_TOKEN {}".format(login_token) }
        if self.authorization:
            return {'Authorization': "TOKEN {}".format(self.authorization) }
        elif self.username and self.password:
            token = '{}:{}'.format(self.username, self.password)
            try:
                token = base64.b64encode(bytes(token, 'UTF-8')).decode('UTF-8')
            except TypeError:
                token = base64.b64encode(token).decode('UTF-8')
            return {'Authorization': "Basic {}".format(token)}

    def _prep_request(self, resource, login_token):
        """
        Creates a header and a url for a given resource

        :param resource: The resource a request is going to be made against
        :return:         The header for the resource and the url to hit
        """
        header = self._get_auth_header(login_token)
        if not isinstance(resource, str):
            resource = '/'.join(str(x) for x in resource)

        url = '{}://{}'.format(self.protocol, self.server_address)
        if self.port:
            url = "{}:{}".format(url, self.port)
        url = "{}/api/{}".format(url, resource)

        return header, url

    @monitor_network
    def get(self, resource, params=None, login_token=None):
        """
        Executes a GET request based on the supplied parameters.

        :raise HTTPError: If non-2xx response value
        :param resource:  The API resource to hit, or a list that will be
                           joined by '/'
        :param params:    The parameters to include in the request
        :return:          The response from the request
        """
        header, url = self._prep_request(resource, login_token)
        response = requests.get(url, params=params, headers=header, verify=self.verify_ssl)
        response.raise_for_status()
        return response

    @monitor_network
    def post(self, resource, params=None, payload=None, login_token=None):
        """
        Executes a POST request based on the supplied parameters.

        :raise HTTPError: If non-2xx response value
        :param resource:  The API resource to hit, or a list that will be
                           joined by '/'
        :param params:    The parameters to include in the request
        :return:          The response from the request
        """
        header, url = self._prep_request(resource, login_token)
        response = requests.post(url, params=params, data=json.dumps(payload), headers=header, verify=self.verify_ssl)
        response.raise_for_status()
        return response

    @monitor_network
    def put(self, resource, params=None, login_token=None):
        """
        Executes a PUT request based on the supplied parameters.

        :raise HTTPError: If non-2xx response value
        :param resource:  The API resource to hit, or a list that will be
                           joined by '/'
        :param params:    The parameters to include in the request
        :return:          The response from the request
        """
        print('put is unused at the moment, and this isn\'t a real implementation. '
              'If you need a real implementation, please update this and add a test.')
        header, url = self._prep_request(resource, login_token)
        response = requests.put(url, params=params, headers=header, verify=self.verify_ssl)
        response.raise_for_status()
        return response

    @monitor_network
    def delete(self, resource, params=None, login_token=None):
        """
        Executes a DELETE request based on the supplied parameters.

        :raise HTTPError: If non-2xx response value
        :param resource:  The API resource to hit, or a list that will be
                           joined by '/'
        :param params:    The parameters to include in the request
        :return:          The response from the request
        """
        print('delete is unused at the moment, and this isn\'t a real implementation. '
              'If you need a real implementation, please update this and add a test.')
        header, url = self._prep_request(resource, login_token)
        response = requests.delete(url, params=params, headers=header, verify=self.verify_ssl)
        response.raise_for_status()
        return response

    def url_name(self):
        """
        Generates a printable string for logging purposes. Only includes the
        port if it's not the default port for the protocol.

        :return: The string describing the server's URL
        """
        if ((self.protocol is 'http' and self.port is '443') or
                (self.protocol is 'https' and self.port is '80') or
                not self.port):
            return u'{}://{}'.format(self.protocol, self.server_address)
        return u'{}://{}:{}'.format(self.protocol, self.server_address, self.port)

    @staticmethod
    def json_from_response(response):
        """
        Abstracts out convoluted steps to get json out of a http response

        :param response: The HTTP response that needs json extracted from it
        :return:         The dictionary the json represents.
        """
        return json.loads(response.content.decode('UTF-8'))

    def fetch_all_paged(self, resource_name, params, key):
        """Yields items from a paged request."""
        def request(current_page):
            """Executes a request for the next page of results and returns them"""
            params['pgNum'] = str(current_page)
            response = self.get(resource_name, params)
            content = self.json_from_response(response)
            try:
                return content['data'][key]
            except KeyError:
                return []

        page_number = 1
        results = True
        while results:
            results = request(page_number)
            page_number += 1
            for result in results:
                yield result

    def __str__(self):
        return "Server:{0}".format(self.url_name())
