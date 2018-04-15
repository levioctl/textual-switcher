import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
gi.require_version('Wnck', '3.0')
from gi.repository import Wnck, GLib

import glib_wrappers


class Window(object):
    BROWSERS_WM_CLASSES = ["Navigator.Firefox", "google-chrome.Google-chrome"]

    def __init__(self):
        self.xid = None
        self.pid = None
        self.wm_class = None
        self.title = None
        self.destkop_id = None
        self.hostname = None

    def is_browser(self):
        return self.wm_class in self.BROWSERS_WM_CLASSES


class WindowControl(object):
    LIST_WINDOWS_COMMAND = ["wmctrl", "-lpx"]

    def async_list_windows(self, callback):
        stdout = glib_wrappers.async_run_subprocess(self.LIST_WINDOWS_COMMAND)
        io = GLib.IOChannel(stdout)

        def list_windows_callback(*_, **__):
            output = io.read()
            windows = self.parse_wlist_output(output)
            icons = self._get_icons()
            for window in windows:
                window.icon = icons.get(window.xid, None)
            callback(windows)

        io.add_watch(GLib.IO_IN | GLib.IO_HUP, list_windows_callback)

    @staticmethod
    def focus_on_window(window_id):
        window_id = hex(window_id)
        command = ["wmctrl", "-ia", window_id]
        glib_wrappers.async_run_subprocess(command)

    def async_focus_on_window(self, window_id):
        window_id = hex(window_id)
        command = ["wmctrl", "-iR", window_id]
        glib_wrappers.async_run_subprocess(command)

    @staticmethod
    def parse_wlist_output(wlist_output):
        windows = list()
        for line in wlist_output.splitlines():
            window = Window()
            xid_hex_str, line = line.split(" ", 1)
            window.xid = int(xid_hex_str, 16)
            line = line.lstrip()
            window.desktop_id, line = line.split(" ", 1)
            line = line.lstrip()
            pid_str, line = line.split(" ", 1)
            window.pid = int(pid_str)
            line = line.lstrip()
            window.wm_class, line = line.split(" ", 1)
            if window.wm_class == "N/A":
                continue
            line = line.lstrip()
            window.hostname, line = line.split(" ", 1)
            if window.title == "Desktop":
                continue
            window.title = line.lstrip()
            windows.append(window)
        return windows

    def _get_icons(self):
        screen = Wnck.Screen.get_default()
        # The following is needed in order to wait for windows to ready
        while Gtk.events_pending():
            Gtk.main_iteration()
        screen.force_update()
        icons = {w.get_xid(): w.get_icon() for w in screen.get_windows()}
        return icons
