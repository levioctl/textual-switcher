import subprocess


class WindowManager(object):
    LIST_WINDOWS_COMMAND = ["wmctrl", "-lpx"]

    def __init__(self, glib):
        self._glib = glib

    def async_list_windows(self, callback):
        _, _, stdout, _ = self._glib.spawn_async(self.LIST_WINDOWS_COMMAND,
            flags=self._glib.SpawnFlags.SEARCH_PATH|self._glib.SpawnFlags.DO_NOT_REAP_CHILD,
            standard_output=True,
            standard_error=True)
        io = self._glib.IOChannel(stdout)

        def parse_window_list_callback(*_, **__):
            output = io.read()
            windows = self.parse_wlist_output(output)
            callback(windows)

        io.add_watch(self._glib.IO_IN|self._glib.IO_HUP, parse_window_list_callback)

    @staticmethod
    def focus_on_window(window_id):
        window_id = hex(window_id)
        cmd = ["wmctrl", "-ia", window_id]
        subprocess.check_call(cmd)

    def async_focus_on_window(self, window_id):
        window_id = hex(window_id)
        params = ["wmctrl", "-iR", window_id]
        self._glib.spawn_async(
            params,
            flags=self._glib.SpawnFlags.SEARCH_PATH|self._glib.SpawnFlags.DO_NOT_REAP_CHILD,
            standard_output=True,
            standard_error=True)

    @staticmethod
    def parse_wlist_output(wlist_output):
        windows = list()
        for line in wlist_output.splitlines():
            xid, line = line.split(" ", 1)
            line = line.lstrip()
            desktop_id, line = line.split(" ", 1)
            del desktop_id
            line = line.lstrip()
            pid, line = line.split(" ", 1)
            pid = int(pid)
            line = line.lstrip()
            wm_class, line = line.split(" ", 1)
            if wm_class == "N/A":
                continue
            line = line.lstrip()
            hostname, line = line.split(" ", 1)
            del hostname
            title = line.lstrip()
            if title == "Desktop":
                continue
            window = [xid, pid, wm_class, title]
            windows.append(window)
        return windows
