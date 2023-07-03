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
A collection of basic helper functions for several scripts.
"""

# pylint: disable=import-error
import sys
import contextlib
import os
import functools


@contextlib.contextmanager
def smart_open(filename, overwrite=False):
    """
    Opens a file if there is a filename, otherwise defaults to stdout and will
    automatically close the file once it's done being used.

    :param filename:  Maybe a filename
    :param overwrite: Whether or not to overwrite said file or to append
    :return:          Yields either an open file or stdout based on input
    """
    if filename and filename != '-':
        style = 'w' if overwrite else 'a'
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        handle = open(filename, style)
    else:
        handle = sys.stdout

    try:
        yield handle
    finally:
        if handle is not sys.stdout:
            handle.close()


# decorator
def memoize(func):
    """
    A decorator that caches output based on input.

    :param func: The function to cache the results of
    :return:     The new function with the cache built in
    """
    memo = {}

    @functools.wraps(func)
    def memoized_func(*args, **kwargs):
        """
        The wrapper function for the memoize decorator
        """
        if args not in memo:
            result = func(*args, **kwargs)
            if result:
                memo[args] = result
        return memo[args]

    return memoized_func
