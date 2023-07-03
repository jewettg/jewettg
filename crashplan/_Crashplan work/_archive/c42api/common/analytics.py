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
Functions for collecting useful data.
"""

import json
import os
import sys
from threading import Lock
import functools
import tempfile
import shutil

OUTPUT_DIRECTORY = None
_LOCK = Lock()


# decorator
def with_lock(func):
    """
    Every function that leverages analytics needs to be decorated.

    :param func: The function to decorate that uses OUTPUT_DIRECTORY
    :return:     A wrapped version of the function that's threadsafe
    """
    @functools.wraps(func)
    def wrapper_func(*args, **kwargs):
        """
        The wrapper for the function that uses a lock
        """
        # if this isn't going to result in analytics, don't lock the thread.
        if not OUTPUT_DIRECTORY:
            return func(*args, **kwargs)
        with _LOCK:
            return func(*args, **kwargs)
    return wrapper_func


def _count_lines(file_path):
    """
    Method for counting lines in a file without blowing out memory

    :param file_path: The path of the file to count the lines of
    :return:          The number of lines in the file
    """
    try:
        with open(file_path, 'r') as to_count:
            return sum(1 for _ in to_count)
    except IOError:
        return 0


def _roll_over_file(file_path):
    """
    Method for removing the first line of a file without blowing out memory

    :param file_path: The path of the file to remove the first line of
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    with open(file_path, 'r') as old_file, temp_file as rolled_file:
        old_file.next()
        for line in old_file:
            rolled_file.write(line)
    shutil.copy(temp_file.name, file_path)
    os.remove(temp_file.name)


def write_json_analytics(file_name, analytic_dict,
                         size_limit=sys.maxint, result_limit=sys.maxint):
    """
    Writes out a json dictionary as part of a larger array.

    :param file_name:     The file name to dump the json
    :param analytic_dict: The dictionary to be written out
    """
    if not OUTPUT_DIRECTORY:
        return
    if size_limit == sys.maxint and result_limit == sys.maxint:
        # Limitless growth is disallowed
        return
    file_name += '.json'
    path = os.path.join(OUTPUT_DIRECTORY, file_name)

    try:
        size = os.stat(path).st_size
    except OSError:
        size = 0
    remove_first_line = (size > size_limit or
                         _count_lines(path) >= result_limit)
    if remove_first_line:
        _roll_over_file(path)
        size = os.stat(path).st_size

    with open(path, 'a+') as out:
        if size:
            out.write('\n')
        json.dump(analytic_dict, out)
