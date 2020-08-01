import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
gi.require_version('Wnck', '3.0')
from gi.repository import Wnck, GLib

import glib_wrappers
from utils import window


LIST_WINDOWS_COMMAND = ["wmctrl", "-lpx"]


def _get_icons():
    screen = Wnck.Screen.get_default()
    # The following is needed in order to wait for windows to ready
    while Gtk.events_pending():
        Gtk.main_iteration()
    screen.force_update()
    icons = {w.get_xid(): w.get_icon() for w in screen.get_windows()}
    return icons


def async_list_windows(callback):
    stdout = glib_wrappers.async_run_subprocess(LIST_WINDOWS_COMMAND)
    io = GLib.IOChannel(stdout)

    def list_windows_callback(*_, **__):
        output = io.read()
        windows = parse_wlist_output(output)
        icons = _get_icons()
        for _window in windows:
            _window.icon = icons.get(_window.xid, None)
        callback(windows)

    io.add_watch(GLib.IO_IN | GLib.IO_HUP, list_windows_callback)


def focus_on_window(window_id):
    window_id = hex(window_id)
    command = ["wmctrl", "-ia", window_id]
    glib_wrappers.async_run_subprocess(command)


def async_focus_on_window(window_id):
    window_id = hex(window_id)
    command = ["wmctrl", "-iR", window_id]
    glib_wrappers.async_run_subprocess(command)


def parse_wlist_output(wlist_output):
    windows = list()
    for line in wlist_output.splitlines():
        _window = window.Window()
        xid_hex_str, line = line.split(" ", 1)
        _window.xid = int(xid_hex_str, 16)
        line = line.lstrip()
        _window.desktop_id, line = line.split(" ", 1)
        line = line.lstrip()
        pid_str, line = line.split(" ", 1)
        _window.pid = int(pid_str)
        line = line.lstrip()
        _window.wm_class, line = line.split(" ", 1)
        if _window.wm_class == "N/A":
            continue
        line = line.lstrip()
        _window.hostname, line = line.split(" ", 1)
        if _window.title == "Desktop":
            continue
        _window.title = line.lstrip()
        windows.append(_window)
    return windows
