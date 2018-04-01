import os
import json
import struct
import os.path
import unicodedata
from gi.repository import GLib


class ApiProxyNotReady(Exception): pass


class TabControl(object):
    API_PROXY_NAMED_PIPES_DIR = os.path.join('/run', 'user', str(os.getuid()), "textual-switcher-proxy")
    OUT_PIPE_FILENAME = os.path.join(API_PROXY_NAMED_PIPES_DIR, "textual_switcher_to_api_proxy_for_firefox_pid_%d")
    IN_PIPE_FILENAME = os.path.join(API_PROXY_NAMED_PIPES_DIR, "api_proxy_to_textual_switcher_for_firefox_pid_%d")

    def __init__(self, update_tabs_callback):
        self._in_fds_by_browser_pid = dict()
        self._out_fds_by_browser_pid = dict()
        self._update_tabs_callback = update_tabs_callback
        self._in_id = None

    def async_list_browser_tabs(self, active_browsers_pids):
        for pid in active_browsers_pids:
            if not self._is_connected_to_api_proxy_for_browser_pid(pid):
                try:
                    self._in_id = self._connect_to_api_for_browser_pid(pid)
                except ApiProxyNotReady:
                    continue

            self._activate_callback_for_one_message_from_api_proxy(pid)
            self.send_list_tabs_command(pid)

        self._clean_stale_descriptors(active_browsers_pids)

    def _activate_callback_for_one_message_from_api_proxy(self, pid):
        in_fd = self._in_fds_by_browser_pid[pid]
        GLib.io_add_watch(in_fd, GLib.IO_IN, self._receive_message_from_api_proxy)

    def _is_connected_to_api_proxy_for_browser_pid(self, pid):
        return pid in self._in_fds_by_browser_pid and pid in self._out_fds_by_browser_pid

    def _connect_to_api_for_browser_pid(self, pid):
        in_pipe_filename = self.IN_PIPE_FILENAME % (pid,)
        try:
            self._in_fds_by_browser_pid[pid] = os.open(in_pipe_filename, os.O_RDONLY | os.O_NONBLOCK)
        except:
            raise ApiProxyNotReady(pid)

        out_pipe_filename = self.OUT_PIPE_FILENAME % (pid,)
        try:
            self._out_fds_by_browser_pid[pid] = os.open(out_pipe_filename, os.O_WRONLY | os.O_NONBLOCK)
        except:
            raise ApiProxyNotReady(pid)

    def _receive_message_from_api_proxy(self, fd, cond):
        browser_pid = [pid for pid, in_fd in self._in_fds_by_browser_pid.iteritems() if fd == in_fd]
        if not browser_pid or len(browser_pid) > 1:
            print 'invalid browser pid', browser_pid
            return
        browser_pid = browser_pid[0]
        content = self._read_from_api_proxy(fd)
        if content is not None:
            tabs = json.loads(content)
            for tab in tabs:
                tab['title'] = unicodedata.normalize('NFKD', tab['title']).encode('ascii', 'ignore')
            print 'receiving message from api proxy', len(tabs)
            self._update_tabs_callback(pid, tabs)

    @staticmethod
    def _read_from_api_proxy(fd):
        message = os.read(fd, 4096)
        raw_length = message[:4]
        if not raw_length:
            return None
        length = struct.unpack('@I', raw_length)[0]
        payload = message[4:4 + length]
        if len(payload) != length:
            return None
        return payload

    def send_list_tabs_command(self, pid):
        os.write(self._out_fds_by_browser_pid[pid], 'list_tabs')

    def _clean_stale_descriptors(self, active_browsers_pids):
        stale_pids = [pid for pid in active_browsers_pids if
                      pid not in self._in_fds_by_browser_pid and
                      pid not in self._out_fds_by_browser_pid]

        for pid in stale_pids:
            self._clean_fds_for_browser_pid(stale_pids, self._in_fds_by_browser_pid)
            self._clean_fds_for_browser_pid(stale_pids, self._out_fds_by_browser_pid)

    def _clean_fds_for_browser_pid(self, browser_pids, pid_to_fd):
        stale_pids_in_dict = [pid for pid in browser_pids if pid in pid_to_fd]
        for pid in stale_pids_in_dict:
            fd = pid_to_fd[pid]
            try:
                os.close(fd)
            except:
                pass
            del pid_to_fd[pid]
