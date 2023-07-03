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
A collection of functions related to script output.
"""

# pylint: disable=import-error
import json

from c42csv import c42_csv as csv


def write_csv(out, json_list, header=False, shallow=False, keyset=None):
    """
    Print a json list as csv. Rather than have to create an entire list in
    memory, this prints out each element of the list individually.
    :param out:       The file in which to print (or stdout)
    :param json_list: An iterable containing things that can be dumped by json
                       (typically lists or dicts)
    :param header:    Whether or not to include a csv header in the output
    :param shallow:   Whether or not to shallow parse. If True, only parse the
                       top level keys, and use the child value as the value,
                       event if it is a dictionary or list. Default is False.
    :param keyset:    A pre-populated KeySet object specifying how to write
                       the items in json_list to the csv file. Ignore this
                       if you want the KeySet to be generated for you.
    """
    if not keyset:
        keyset = csv.KeySet()
    for item in json_list:
        if not keyset:
            for key, value in item.items():
                json_key = csv.create_key(key, value, shallow)
                keyset.add_key(json_key)
            if header:
                write_header_from_keyset(keyset, out)
        values = []
        for top_level_key in keyset.all_keys():
            values = values + csv.dict_into_values(item, top_level_key, 0, shallow)
        csv_string = csv.create_csv_string(values)
        out.write(csv_string.encode('UTF-8') + '\n')


def write_header_from_keyset(keyset, out):
    """
    Uses the c42csv library to create a header based on the input keys
    :param keyset: The KeySet used to generate the header
    :param out:    The opened file to print the header
    """
    key_header = []
    for top_level_key in keyset.all_keys():
        key_header = csv.flattened_keys(top_level_key, key_header)
    out.write(",".join(key_header).encode('UTF-8') + "\n")


def write_json(out, json_list):
    """
    Print a json list. Rather than have to create an entire list in memory
    this prints out each element of the list individually.
    :param out:       The file in which to print (or stdout)
    :param json_list: An iterable containing things that can be dumped by json
                       (typically lists or dicts)
    """
    out.write('[\n')
    first = True
    for item in json_list:
        if not first:
            out.write(',\n')
        first = False
        line = json.dumps(item)
        out.write(line)
    out.write('\n]\n')


def write_json_splunk(out, json_list):
    """
    Print a json list. Rather than have to create an entire list in memory
    this prints out each element of the list individually. Unlike write_json(),
    this will only write dictionaries, making it improper json.
    :param out:       The file in which to print (or stdout)
    :param json_list: An iterable containing things that can be dumped by json
                       (typically lists or dicts)
    """
    for item in json_list:
        line = json.dumps(item)
        out.write(line + "\n")
