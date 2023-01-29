#!/usr/bin/env python

# -*- coding: utf-8 -*-

# This file is part of Tautulli.
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

import os
import sys

# Ensure lib added to path, before any other imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

from future.builtins import str

import appdirs
import argparse
import datetime
import locale
import pytz
import signal
import shutil
import time
import threading
import tzlocal

import jellypy
from jellypy import common, config, database, helpers, logger, webstart
if common.PLATFORM == 'Windows':
    from jellypy import windows
elif common.PLATFORM == 'Darwin':
    from jellypy import macos

# Register signals, such as CTRL + C
signal.signal(signal.SIGINT, jellypy.sig_handler)
signal.signal(signal.SIGTERM, jellypy.sig_handler)


def main():
    """
    JellyPy application entry point. Parses arguments, setups encoding and
    initializes the application.
    """

    # Fixed paths to JellyPy
    if hasattr(sys, 'frozen') and hasattr(sys, '_MEIPASS'):
        jellypy.FROZEN = True
        jellypy.FULL_PATH = os.path.abspath(sys.executable)
        jellypy.PROG_DIR = sys._MEIPASS
    else:
        jellypy.FULL_PATH = os.path.abspath(__file__)
        jellypy.PROG_DIR = os.path.dirname(jellypy.FULL_PATH)

    jellypy.ARGS = sys.argv[1:]

    # From sickbeard
    jellypy.SYS_PLATFORM = sys.platform
    jellypy.SYS_ENCODING = None

    try:
        locale.setlocale(locale.LC_ALL, "")
        jellypy.SYS_LANGUAGE, jellypy.SYS_ENCODING = locale.getdefaultlocale()
    except (locale.Error, IOError):
        pass

    # for OSes that are poorly configured I'll just force UTF-8
    if not jellypy.SYS_ENCODING or jellypy.SYS_ENCODING in ('ANSI_X3.4-1968', 'US-ASCII', 'ASCII'):
        jellypy.SYS_ENCODING = 'UTF-8'

    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(description='A Python based monitoring and tracking tool for Jellyfin Server.')

    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument(
        '-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument(
        '-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument(
        '-p', '--port', type=int, help='Force JellyPy to run on a specified port')
    parser.add_argument(
        '--dev', action='store_true', help='Start JellyPy in the development environment')
    parser.add_argument(
        '--datadir', help='Specify a directory where to store your data files')
    parser.add_argument(
        '--config', help='Specify a config file to use')
    parser.add_argument(
        '--nolaunch', action='store_true', help='Prevent browser from launching on startup')
    parser.add_argument(
        '--pidfile', help='Create a pid file (only relevant when running as a daemon)')
    parser.add_argument(
        '--nofork', action='store_true', help='Start JellyPy as a service, do not fork when restarting')

    args = parser.parse_args()

    if args.verbose:
        jellypy.VERBOSE = True
    if args.quiet:
        jellypy.QUIET = True

    # Do an intial setup of the logger.
    # Require verbose for pre-initilization to see critical errors
    logger.initLogger(console=not jellypy.QUIET, log_dir=False, verbose=True)

    try:
        jellypy.SYS_TIMEZONE = tzlocal.get_localzone()
    except (pytz.UnknownTimeZoneError, LookupError, ValueError) as e:
        logger.error("Could not determine system timezone: %s" % e)
        jellypy.SYS_TIMEZONE = pytz.UTC

    jellypy.SYS_UTC_OFFSET = datetime.datetime.now(jellypy.SYS_TIMEZONE).strftime('%z')

    if helpers.bool_true(os.getenv('JELLYPY_DOCKER', False)):
        jellypy.DOCKER = True
        jellypy.DOCKER_MOUNT = not os.path.isfile('/config/DOCKER')
    if helpers.bool_true(os.getenv('TAUTULLI_SNAP', False)):
        jellypy.SNAP = True

    if args.dev:
        jellypy.DEV = True
        logger.debug("JellyPy is running in the dev environment.")

    if args.daemon:
        if sys.platform == 'win32':
            logger.warn("Daemonizing not supported under Windows, starting normally")
        else:
            jellypy.DAEMON = True
            jellypy.QUIET = True

    if args.nofork:
        jellypy.NOFORK = True
        logger.info("JellyPy is running as a service, it will not fork when restarted.")

    if args.pidfile:
        jellypy.PIDFILE = str(args.pidfile)

        # If the pidfile already exists, jellypy may still be running, so
        # exit
        if os.path.exists(jellypy.PIDFILE):
            try:
                with open(jellypy.PIDFILE, 'r') as fp:
                    pid = int(fp.read())
            except IOError as e:
                raise SystemExit("Unable to read PID file: %s", e)

            try:
                os.kill(pid, 0)
            except OSError:
                logger.warn("PID file '%s' already exists, but PID %d is "
                            "not running. Ignoring PID file." %
                            (jellypy.PIDFILE, pid))
            else:
                # The pidfile exists and points to a live PID. jellypy may
                # still be running, so exit.
                raise SystemExit("PID file '%s' already exists. Exiting." %
                                 jellypy.PIDFILE)

        # The pidfile is only useful in daemon mode, make sure we can write the
        # file properly
        if jellypy.DAEMON:
            jellypy.CREATEPID = True

            try:
                with open(jellypy.PIDFILE, 'w') as fp:
                    fp.write("pid\n")
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s", e)
        else:
            logger.warn("Not running in daemon mode. PID file creation " \
                        "disabled.")

    # Determine which data directory and config file to use
    if args.datadir:
        jellypy.DATA_DIR = args.datadir
    elif jellypy.FROZEN:
        jellypy.DATA_DIR = appdirs.user_data_dir("JellyPy", False)
    else:
        jellypy.DATA_DIR = jellypy.PROG_DIR

    # Migrate Snap data dir
    if jellypy.SNAP:
        snap_common = os.environ['SNAP_COMMON']
        old_data_dir = os.path.join(snap_common, 'JellyPy')
        if os.path.exists(old_data_dir) and os.listdir(old_data_dir):
            jellypy.SNAP_MIGRATE = True
            logger.info("Migrating Snap user data.")
            shutil.move(old_data_dir, jellypy.DATA_DIR)

    if args.config:
        config_file = args.config
    else:
        config_file = os.path.join(jellypy.DATA_DIR, config.FILENAME)

    # Try to create the DATA_DIR if it doesn't exist
    if not os.path.exists(jellypy.DATA_DIR):
        try:
            os.makedirs(jellypy.DATA_DIR)
        except OSError:
            raise SystemExit(
                'Could not create data directory: ' + jellypy.DATA_DIR + '. Exiting....')

    # Make sure the DATA_DIR is writeable
    test_file = os.path.join(jellypy.DATA_DIR, '.TEST')
    try:
        with open(test_file, 'w'):
            pass
    except IOError:
        raise SystemExit(
            'Cannot write to the data directory: ' + jellypy.DATA_DIR + '. Exiting...')
    finally:
        try:
            os.remove(test_file)
        except OSError:
            pass

    # Put the database in the DATA_DIR
    jellypy.DB_FILE = os.path.join(jellypy.DATA_DIR, database.FILENAME)

    # Move 'jellypy.db' to 'tautulli.db'
    if os.path.isfile(os.path.join(jellypy.DATA_DIR, 'jellypy.db')) and \
            not os.path.isfile(os.path.join(jellypy.DATA_DIR, jellypy.DB_FILE)):
        try:
            os.rename(os.path.join(jellypy.DATA_DIR, 'jellypy.db'), jellypy.DB_FILE)
        except OSError as e:
            raise SystemExit("Unable to rename jellypy.db to tautulli.db: %s", e)

    if jellypy.DAEMON:
        jellypy.daemonize()

    # Read config and start logging
    jellypy.initialize(config_file)

    # Start the background threads
    jellypy.start()

    # Force the http port if neccessary
    if args.port:
        jellypy.HTTP_PORT = args.port
        logger.info('Using forced web server port: %i', jellypy.HTTP_PORT)
    else:
        jellypy.HTTP_PORT = int(jellypy.CONFIG.HTTP_PORT)

    # Check if pyOpenSSL is installed. It is required for certificate generation
    # and for CherryPy.
    if jellypy.CONFIG.ENABLE_HTTPS:
        try:
            import OpenSSL
        except ImportError:
            logger.warn("The pyOpenSSL module is missing. Install this "
                        "module to enable HTTPS. HTTPS will be disabled.")
            jellypy.CONFIG.ENABLE_HTTPS = False

    # Try to start the server. Will exit here is address is already in use.
    webstart.start()

    if common.PLATFORM == 'Windows':
        if jellypy.CONFIG.SYS_TRAY_ICON:
            jellypy.WIN_SYS_TRAY_ICON = windows.WindowsSystemTray()
            jellypy.WIN_SYS_TRAY_ICON.start()
        windows.set_startup()
    elif common.PLATFORM == 'Darwin':
        macos.set_startup()

    # Open webbrowser
    if jellypy.CONFIG.LAUNCH_BROWSER and not args.nolaunch and not jellypy.DEV:
        jellypy.launch_browser(jellypy.CONFIG.HTTP_HOST, jellypy.HTTP_PORT,
                              jellypy.HTTP_ROOT)

    if common.PLATFORM == 'Darwin' and jellypy.CONFIG.SYS_TRAY_ICON:
        if not macos.HAS_PYOBJC:
            logger.warn("The pyobjc module is missing. Install this "
                        "module to enable the MacOS menu bar icon.")
            jellypy.CONFIG.SYS_TRAY_ICON = False

        if jellypy.CONFIG.SYS_TRAY_ICON:
            # MacOS menu bar icon must be run on the main thread and is blocking
            # Start the rest of JellyPy on a new thread
            thread = threading.Thread(target=wait)
            thread.daemon = True
            thread.start()

            jellypy.MAC_SYS_TRAY_ICON = macos.MacOSSystemTray()
            jellypy.MAC_SYS_TRAY_ICON.start()
        else:
            wait()
    else:
        wait()


def wait():
    logger.info("JellyPy is ready!")

    # Wait endlessly for a signal to happen
    while True:
        if not jellypy.SIGNAL:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                jellypy.SIGNAL = 'shutdown'
        else:
            logger.info('Received signal: %s', jellypy.SIGNAL)

            if jellypy.SIGNAL == 'shutdown':
                jellypy.shutdown()
            elif jellypy.SIGNAL == 'restart':
                jellypy.shutdown(restart=True)
            elif jellypy.SIGNAL == 'checkout':
                jellypy.shutdown(restart=True, checkout=True)
            elif jellypy.SIGNAL == 'reset':
                jellypy.shutdown(restart=True, reset=True)
            elif jellypy.SIGNAL == 'update':
                jellypy.shutdown(restart=True, update=True)
            else:
                logger.error('Unknown signal. Shutting down...')
                jellypy.shutdown()

            jellypy.SIGNAL = None


if __name__ == "__main__":
    main()
