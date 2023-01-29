# -*- coding: utf-8 -*-

#  This file is part of Tautulli.
#
#  Tautulli is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Tautulli is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Tautulli.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import os
import re
from datetime import date
from io import open

import jellypy
from jellypy import helpers
from jellypy import logger


def list_jellyfin_logs():
    logs_dir = jellypy.CONFIG.JELLYFIN_LOGS_FOLDER

    if not logs_dir or logs_dir and not os.path.exists(logs_dir):
        return []

    log_files = []
    for file in os.listdir(logs_dir):
        if file.startswith('Plex Transcoder Statistics'):
            # Plex Transcoder Statistics is an XML file
            continue
        if os.path.isfile(os.path.join(logs_dir, file)):
            name, ext = os.path.splitext(file)
            if ext == '.log' and not name[-1].isdigit():
                log_files.append(name)

    return log_files


def get_log_tail(window=20, parsed=True, log_file=''):
    if not jellypy.CONFIG.JELLYFIN_LOGS_FOLDER:
        return []
    today = date.today()

    log_file = (log_file or f'log_{today.strftime("%Y%m%d")}') + '.log'
    log_file = os.path.join(jellypy.CONFIG.JELLYFIN_LOGS_FOLDER, log_file)

    try:
        logfile = open(log_file, 'r', encoding='utf-8')
    except IOError as e:
        logger.error('Unable to open Jellyfin Log file. %s' % e)
        return []

    log_lines = tail(logfile, window)

    if parsed:
        line_error = False
        clean_lines = []
        for i in log_lines:
            if not i.strip():
                continue
            try:
                """ Original
                # log_time = i.split(' [')[0]
                #log_level = i.split('] ', 1)[1].split(' - ', 0)[0]
                # log_msg = i.split('] ', 1)[1].split(' - ', 1)[1]
                """
                log_time = \
                    re.findall("\\d{4}-?\\d{1,2}-?\\d{1,2} \\d{1,2}:\\d{1,2}:\\d{1,2}[.]?\\d{1,3} [+]\\d{1,2}:\\d{1,2}",
                               i)[
                        -1]
                log_level = re.findall(r"\[([A-Za-z]+)\]", i)[-1]

                if log_level == "INF":
                    log_level = "INFO"
                elif log_level == "ERR":
                    log_level = "ERROR"
                elif log_level == "WRN":
                    log_level = "WARN"

                log_module = re.findall(r"\S[^:\s]+[^:\s]+[^:\s]+(?=:)", i)[0]
                log_msg_num = re.findall(r"\[([0-9_]+)\]", i)[-1]

                try:
                    log_msg = f"{log_module} :: {i.split(f' [{log_msg_num}] ', 1)[1].split(': ')[1]} {i.split(f' [{log_msg_num}] ', 1)[1].split(': ')[2]}"
                except IndexError:
                    log_msg = f"{log_module} :: {i.split(f' [{log_msg_num}] ', 1)[1].split(': ')[1]}"

                full_line = [log_time, log_level, log_msg]
                clean_lines.append(full_line)
            except:
                line_error = True
                full_line = ['', '', 'Unable to parse log line.']
                clean_lines.append(full_line)

        if line_error:
            logger.error('JellyPy was unable to parse some lines of the Jellyfin log.')

        return clean_lines
    else:
        raw_lines = []
        for i in log_lines:
            raw_lines.append(helpers.latinToAscii(i))

        return raw_lines


# http://stackoverflow.com/a/13790289/2405162
def tail(f, lines=1, _buffer=4098):
    """Tail a file and get X lines from the end"""
    # place holder for the lines found
    lines_found = []

    # block counter will be multiplied by buffer
    # to get the block size from the end
    block_counter = -1

    # loop until we find X lines
    while len(lines_found) < lines:
        try:
            f.seek(block_counter * _buffer, os.SEEK_END)
        except IOError:  # either file is too small, or too many lines requested
            f.seek(0)
            lines_found = f.readlines()
            break

        lines_found = f.readlines()

        # we found enough lines, get out
        if len(lines_found) > lines:
            break

        # decrement the block counter to get the
        # next X bytes
        block_counter -= 1

    return lines_found[-lines:]
