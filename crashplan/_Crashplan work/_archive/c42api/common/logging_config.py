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
Tools for configuring logging with c42api.
"""

import logging
import os
import sys

LOG_PREFIX = 'c42'
_BASE_LOGGER = logging.getLogger(LOG_PREFIX)


class LogConfigurator(object):
    """
    A class for holding the logger state.
    """
    def __init__(self, log_level, log_file):
        """
        LogConfigurator initializer
        """
        self._log_level = log_level
        self._log_file = log_file
        self.configure_logging()

    @property
    def log_level(self):
        """Getter for the mutable property log_level"""
        return self._log_level

    @log_level.setter
    def log_level(self, value):
        """Setter for the mutable property log_level"""
        self._log_level = value
        self.configure_logging()

    @property
    def log_file(self):
        """Getter for the mutable property log_file"""
        return self._log_file

    @log_file.setter
    def log_file(self, value):
        """Setter for the mutable property log_file"""
        self._log_file = value
        self.configure_logging()

    def configure_logging(self):
        """
        Configures logging for all loggers in the logging namespace of
        LOG_PREFIX. The logic below essentially says that if there's a log
        file, log to it and log all errors to stderr, otherwise log to stderr
        or stdout only, depending on log level.
        """
        handler_err = logging.StreamHandler(sys.stderr)
        handler_err.level = logging.ERROR
        handlers = [handler_err]
        if self.log_file:
            if not os.path.exists(os.path.dirname(self.log_file)):
                print self.log_file
                os.makedirs(os.path.dirname(self.log_file))
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(logging.Formatter('[%(asctime)s %(levelname)s %(threadName)s %(module)s] %(message)s'))
            handlers.append(file_handler)

        elif self._log_level < logging.ERROR:
            handler_out = logging.StreamHandler(sys.stdout)
            handlers = [handler_out]

        _BASE_LOGGER.handlers = handlers
        _BASE_LOGGER.level = self._log_level


_LOG_CONFIG = LogConfigurator(logging.INFO, None)


def set_log_level(log_level):
    """
    Setter for the log_level across all files in c42api
    """
    _LOG_CONFIG.log_level = log_level


def set_log_file(log_file):
    """
    Setter for the log_file across all files in c42api
    """
    _LOG_CONFIG.log_file = log_file


def get_logger(logger_name):
    """
    Function to allow files to get their namespaced logger.
    """
    return logging.getLogger(LOG_PREFIX + '.' + logger_name)
