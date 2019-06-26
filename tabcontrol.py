import os
import json
import struct
import os.path
import unicodedata
import expiringdict
import glib_wrappers
from gi.repository import GLib, Gio
from gi.repository.GdkPixbuf import Pixbuf


class ApiProxyNotReady(Exception): pass


class TabControl(object):
    API_PROXY_NAMED_PIPES_DIR = os.path.join('/run', 'user', str(os.getuid()), "textual-switcher-proxy")
    OUT_PIPE_FILENAME = os.path.join(API_PROXY_NAMED_PIPES_DIR, "textual_switcher_to_api_proxy_for_firefox_pid_%d")
    IN_PIPE_FILENAME = os.path.join(API_PROXY_NAMED_PIPES_DIR, "api_proxy_to_textual_switcher_for_firefox_pid_%d")
    ONE_MONTH_IN_SECONDS = 60 * 60 * 24 * 7 * 4

    def __init__(self, update_tabs_callback, update_tab_icon_callback):
        self._in_fds_by_browser_pid = dict()
        self._out_fds_by_browser_pid = dict()
        self._update_tabs_callback = update_tabs_callback
        self._update_tab_icon_callback = update_tab_icon_callback
        self._in_id = None
        self._icon_cache = expiringdict.ExpiringDict(max_len=100, max_age_seconds=self.ONE_MONTH_IN_SECONDS)
        self._retry_counter_by_browser = dict()
        self._is_updated_by_browser = dict()

    def async_list_browsers_tabs(self, active_browsers):
        for browser in active_browsers:
            self._retry_counter_by_browser[browser.pid] = 10
            self._is_updated_by_browser[browser.pid] = False
            GLib.timeout_add(100, self._async_list_browser_tabs, browser)

    def _async_list_browser_tabs(self, browser):
        whether_to_repeat = True

        if self._is_updated_by_browser[browser.pid]:
            whether_to_repeat = False
        else:
            # Decrement left retries counters
            self._retry_counter_by_browser[browser.pid] = max(0, self._retry_counter_by_browser[browser.pid] - 1)

            # Eliminate browsers with no retries left
            if self._retry_counter_by_browser[browser.pid] > 0:

                # Validate connection
                is_connected = self._validate_connection_to_browser(browser.pid)
                if is_connected:
                    # Schedule tablist in thread
                    self._activate_callback_for_one_message_from_api_proxy(browser)
                    self.send_list_tabs_command(browser.pid)

                self._clean_stale_descriptors([browser])

            else:
                whether_to_repeat = False

        return whether_to_repeat

    def async_move_to_tab(self, tab_id, pid):
        is_connected = self._validate_connection_to_browser(pid)
        if is_connected:
            command = 'move_to_tab:%d;' % (tab_id)
            os.write(self._out_fds_by_browser_pid[pid], command)

    def _validate_connection_to_browser(self, pid):
        if not self._is_connected_to_api_proxy_for_browser_pid(pid):
            try:
                self._in_id = self._connect_to_api_for_browser_pid(pid)
            except ApiProxyNotReady:
                return False
        return True

    def _activate_callback_for_one_message_from_api_proxy(self, browser):
        in_fd = self._in_fds_by_browser_pid[browser.pid]
        GLib.io_add_watch(in_fd, GLib.IO_IN, self._receive_message_from_api_proxy, browser)

    def _is_connected_to_api_proxy_for_browser_pid(self, pid):
        return pid in self._in_fds_by_browser_pid and pid in self._out_fds_by_browser_pid

    def _connect_to_api_for_browser_pid(self, pid):
        in_pipe_filename = self.IN_PIPE_FILENAME % (pid,)
        try:
            self._in_fds_by_browser_pid[pid] = os.open(in_pipe_filename, os.O_RDONLY | os.O_NONBLOCK)
        except Exception as ex:
            print('raise ApiProxyNotReady1 {}'.format(str(ex)))
            raise ApiProxyNotReady(pid)

        out_pipe_filename = self.OUT_PIPE_FILENAME % (pid,)
        try:
            self._out_fds_by_browser_pid[pid] = os.open(out_pipe_filename, os.O_WRONLY | os.O_NONBLOCK)
        except Exception as ex:
            print('raise ApiProxyNotReady2 {}'.format(str(ex)))
            raise ApiProxyNotReady(pid)

    def _receive_message_from_api_proxy(self, fd, cond, browser):
        pid = [_pid for _pid, _in_fd in self._in_fds_by_browser_pid.iteritems() if fd == _in_fd]
        if not pid or len(pid) > 1:
            print('invalid browser pid', pid)
            return
        pid = pid[0]
        try:
            content = self._read_from_api_proxy(fd)
        except Exception as ex:
            print(str(ex))
            return

        if content is not None:
            try:
                tabs = json.loads(content)
            except:
                print('cannot load json:')
                print(content)
                return
            self._populate_tabs_icons(tabs)
            self._update_tabs_callback(pid, tabs)
            self._is_updated_by_browser[browser.pid] = True

    def _populate_tabs_icons(self, tabs):
        for tab in tabs:
            tab['icon'] = self.get_tab_icon(tab, fetch_if_missing=True)

    def get_tab_icon(self, tab, fetch_if_missing=False):
        icon = None
        if 'favIconUrl' in tab and tab['favIconUrl'] is not None:
            if tab['favIconUrl'] in self._icon_cache:
                icon = self._icon_cache[tab['favIconUrl']]
            else:
                self._icon_cache[tab['favIconUrl']] = None
                url = tab["favIconUrl"]
                for image_prefix in ("data:image/x-icon;base64,",
                                     "data:image/png;base64,"):
                    if url.startswith(image_prefix):
                        image = url[len(image_prefix):]
                        import base64
                        image = base64.b64decode(image)
                        self._tab_icon_ready(url, image)
                        break
                else:
                    glib_wrappers.async_get_url(url, self._tab_icon_ready)
        return icon

    def _tab_icon_ready(self, url, contents):
        try:
            input_stream = Gio.MemoryInputStream.new_from_data(contents, None)
            pixbuf = Pixbuf.new_from_stream(input_stream, None)
        except Exception as ex:
            print "Error fetching icon for URL '%s': %s" % (url, ex.message)
            return
        self._icon_cache[url] = pixbuf
        self._update_tab_icon_callback(url, contents)

    @staticmethod
    def _read_from_api_proxy(fd):
        raw_length = os.read(fd, 4)
        if not raw_length:
            return None
        size_left_to_read = struct.unpack('@I', raw_length)[0]
        message = ""
        while size_left_to_read > 0:
            addition = os.read(fd, size_left_to_read)
            message += addition
            size_left_to_read -= len(addition)
        return message

    def send_list_tabs_command(self, pid):
        os.write(self._out_fds_by_browser_pid[pid], 'list_tabs;')

    def _clean_stale_descriptors(self, active_browsers):
        stale_pids = [browser.pid for browser in active_browsers if
                      browser.pid not in self._in_fds_by_browser_pid and
                      browser.pid not in self._out_fds_by_browser_pid]

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
