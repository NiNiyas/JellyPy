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
from infi.systray import SysTrayIcon

try:
    from shlex import quote as cmd_quote
except ImportError:
    from pipes import quote as cmd_quote

try:
    import winreg
except ImportError:
    import _winreg as winreg

import jellypy
from jellypy import common
from jellypy import logger
from jellypy import versioncheck


class WindowsSystemTray(object):
    def __init__(self):
        self.image_dir = os.path.join(jellypy.PROG_DIR, 'data/interfaces/', jellypy.CONFIG.INTERFACE, 'images')
        self.icon = os.path.join(self.image_dir, 'logo-circle.ico')

        if jellypy.UPDATE_AVAILABLE:
            self.hover_text = common.PRODUCT + ' - Update Available!'
            self.update_title = 'Check for Updates - Update Available!'
        else:
            self.hover_text = common.PRODUCT
            self.update_title = 'Check for Updates'

        if jellypy.CONFIG.LAUNCH_STARTUP:
            launch_start_icon = os.path.join(self.image_dir, 'check-solid.ico')
        else:
            launch_start_icon = None
        if jellypy.CONFIG.LAUNCH_BROWSER:
            launch_browser_icon = os.path.join(self.image_dir, 'check-solid.ico')
        else:
            launch_browser_icon = None

        self.menu = [
            ['Open JellyPy', None, self.tray_open, 'default'],
            ['', None, 'separator', None],
            ['Start JellyPy at Login', launch_start_icon, self.tray_startup, None],
            ['Open Browser when JellyPy Starts', launch_browser_icon, self.tray_browser, None],
            ['', None, 'separator', None],
            [self.update_title, None, self.tray_check_update, None],
            ['Restart', None, self.tray_restart, None]
        ]
        if not jellypy.FROZEN:
            self.menu.insert(6, ['Update', None, self.tray_update, None])

        self.tray_icon = SysTrayIcon(self.icon, self.hover_text, self.menu, on_quit=self.tray_quit)

    def start(self):
        logger.info("Launching Windows system tray icon.")
        try:
            self.tray_icon.start()
        except Exception as e:
            logger.error("Unable to launch system tray icon: %s." % e)

    def shutdown(self):
        self.tray_icon.shutdown()

    def update(self, **kwargs):
        self.tray_icon.update(**kwargs)

    def tray_open(self, tray_icon):
        jellypy.launch_browser(jellypy.CONFIG.HTTP_HOST, jellypy.HTTP_PORT, jellypy.HTTP_ROOT)

    def tray_startup(self, tray_icon):
        jellypy.CONFIG.LAUNCH_STARTUP = not jellypy.CONFIG.LAUNCH_STARTUP
        set_startup()

    def tray_browser(self, tray_icon):
        jellypy.CONFIG.LAUNCH_BROWSER = not jellypy.CONFIG.LAUNCH_BROWSER
        set_startup()

    def tray_check_update(self, tray_icon):
        versioncheck.check_update()

    def tray_update(self, tray_icon):
        if jellypy.UPDATE_AVAILABLE:
            jellypy.SIGNAL = 'update'
        else:
            self.hover_text = common.PRODUCT + ' - No Update Available'
            self.update_title = 'Check for Updates - No Update Available'
            self.menu[5][0] = self.update_title
            self.update(hover_text=self.hover_text, menu_options=self.menu)

    def tray_restart(self, tray_icon):
        jellypy.SIGNAL = 'restart'

    def tray_quit(self, tray_icon):
        jellypy.SIGNAL = 'shutdown'

    def change_tray_update_icon(self):
        if jellypy.UPDATE_AVAILABLE:
            self.hover_text = common.PRODUCT + ' - Update Available!'
            self.update_title = 'Check for Updates - Update Available!'
        else:
            self.hover_text = common.PRODUCT + ' - No Update Available'
            self.update_title = 'Check for Updates'
        self.menu[5][0] = self.update_title
        self.update(hover_text=self.hover_text, menu_options=self.menu)

    def change_tray_icons(self):
        if jellypy.CONFIG.LAUNCH_STARTUP:
            launch_start_icon = os.path.join(self.image_dir, 'check-solid.ico')
        else:
            launch_start_icon = None
        if jellypy.CONFIG.LAUNCH_BROWSER:
            launch_browser_icon = os.path.join(self.image_dir, 'check-solid.ico')
        else:
            launch_browser_icon = None
        self.menu[2][1] = launch_start_icon
        self.menu[3][1] = launch_browser_icon
        self.update(menu_options=self.menu)


def set_startup():
    if jellypy.WIN_SYS_TRAY_ICON:
        jellypy.WIN_SYS_TRAY_ICON.change_tray_icons()

    startup_reg_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"

    exe = sys.executable
    run_args = [arg for arg in jellypy.ARGS if arg != '--nolaunch']
    if jellypy.FROZEN:
        args = [exe] + run_args
    else:
        args = [exe, jellypy.FULL_PATH] + run_args

    registry_key_name = common.PRODUCT

    cmd = ' '.join(cmd_quote(arg) for arg in args).replace('python.exe', 'pythonw.exe').replace("'", '"')

    if jellypy.CONFIG.LAUNCH_STARTUP:
        # Rename old Tautulli registry key
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_reg_path, 0, winreg.KEY_ALL_ACCESS)
            winreg.QueryValueEx(registry_key, f'{common.PRODUCT}_{jellypy.CONFIG.JELLYFIN_UUID}')
            reg_value_exists = True
        except WindowsError:
            reg_value_exists = False

        if reg_value_exists:
            try:
                winreg.DeleteValue(registry_key, f'{common.PRODUCT}_{jellypy.CONFIG.JELLYFIN_UUID}')
                winreg.CloseKey(registry_key)
            except WindowsError:
                pass

        try:
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, startup_reg_path)
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_reg_path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(registry_key, registry_key_name, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(registry_key)
            logger.info("Added JellyPy to Windows system startup registry key.")
            return True
        except WindowsError as e:
            logger.error("Failed to create Windows system startup registry key: %s", e)
            return False

    else:
        # Check if registry value exists
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup_reg_path, 0, winreg.KEY_ALL_ACCESS)
            winreg.QueryValueEx(registry_key, registry_key_name)
            reg_value_exists = True
        except WindowsError:
            reg_value_exists = False

        if reg_value_exists:
            try:
                winreg.DeleteValue(registry_key, registry_key_name)
                winreg.CloseKey(registry_key)
                logger.info("Removed JellyPy from Windows system startup registry key.")
                return True
            except WindowsError as e:
                logger.error("Failed to delete Windows system startup registry key: %s", e)
                return False
