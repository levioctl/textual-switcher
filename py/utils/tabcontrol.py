import os
import json
import struct
import logging
import os.path
import traceback
import unicodedata
from gi.repository import GLib


logger = logging.getLogger(__file__)


class ApiProxyNotReady(Exception): pass


class ApiProxyFdContentionTryAgainLater(Exception): pass


class BrowserTabLister(object):
    API_PROXY_NAMED_PIPES_DIR = os.path.join('/run', 'user', str(os.getuid()), "textual-switcher-proxy")
    OUT_PIPE_FILENAME = os.path.join(API_PROXY_NAMED_PIPES_DIR, "textual_switcher_to_api_proxy_for_firefox_pid_%d")
    IN_PIPE_FILENAME = os.path.join(API_PROXY_NAMED_PIPES_DIR, "api_proxy_to_textual_switcher_for_firefox_pid_%d")

    def __init__(self, pid, update_tabs_callback):
        self.pid = pid
        self._is_updated = True
        self._update_tabs_callback = update_tabs_callback
        self._is_new_list_tab_request = True
        self._nr_retries_left = 1000

        in_pipe_filename = self.IN_PIPE_FILENAME % (pid,)
        try:
            self.in_fd = os.open(in_pipe_filename, os.O_RDONLY | os.O_NONBLOCK)
        except Exception as ex:
            print('Failed to in out FD for browser PID {}: {}'.format(pid, str(ex)))
            raise ApiProxyNotReady(pid)

        out_pipe_filename = self.OUT_PIPE_FILENAME % (pid,)
        try:
            self._out_fd = os.open(out_pipe_filename, os.O_WRONLY | os.O_NONBLOCK)
        except Exception as ex:
            print('Failed to open out FD for browser PID {}: {}'.format(pid, str(ex)))
            print("Cleaning in fd...")
            try:
                os.close(in_fd)
            except:
                print("Failed closing the in FD")
            raise ApiProxyNotReady(pid)

        self.payload = ""
        self.message_length = None
        self._read_leftovers_from_prev_runs__in_pipe()

    def _read_leftovers_from_prev_runs__in_pipe(self):
        while True:
            try:
                os.read(self.in_fd, 1024)
            except OSError as ex:
                if ex.errno == 11:
                    print("No more data in pipe")
                    break
                else:
                    print("Unexpecter error while draining pipe from previous runs:")
                    print(traceback.format_exc())
            except:
                print("Unexpecter error while draining pipe from previous runs:")
                print(traceback.format_exc())

    def read(self):
        # Read length if new payload
        if self.message_length is None:
            #print("{}: Reading length of 4 bytes".format(self.in_fd))
            raw_length = os.read(self.in_fd, 4)
            if not raw_length:
                #print("Invalid raw length")
                return None
            self.message_length = struct.unpack('=I', raw_length)[0]
            #print("{}: New length: {} bytes".format(self.in_fd, self.message_length))

        # Read payload
        read_counter = 0
        while len(self.payload) < self.message_length:
            nr_bytes_left_to_read = self.message_length - len(self.payload)
            try:
                #print('{}: reading 1024 bytes ({} left)'.format(self.in_fd, nr_bytes_left_to_read))
                chunk = os.read(self.in_fd, min(nr_bytes_left_to_read, 1024))
            except IOError as ex:
                if ex.errno == 32:
                    #print("{}: will try again later".format(self.in_fd))
                    raise ApiProxyFdContentionTryAgainLater
                else:
                    raise
            except OSError as ex:
                if ex.errno == 11:
                    #print("{}: will try again later (2)".format(self.in_fd))
                    raise ApiProxyFdContentionTryAgainLater
                else:
                    raise
            self.payload += chunk

            read_counter += 1
            if read_counter >= 99999:
                # Just a warning because this happens sometimes, not sure why
                print("{}: Infinite read from pipe. Dismissing message".format(self.in_fd))
                return None

        # Decode
        try:
            self.payload = self.payload.decode("utf-8")
        except Exception as ex:
            print("{}: Could not decode incoming payload: {}".format(self.in_fd, self.payload))

        result = self.payload
        self.payload = ""
        self.message_length = None
        return result

    def async_move_to_tab(self, tab_id):
        command = 'move_to_tab:%d;' % (tab_id)
        os.write(self._out_fd, command)

    def async_list_tabs(self):
        if self._is_updated:
            self._is_updated = False
            self._is_new_list_tab_request = True

            # Schedule tablist in thread
            self._activate_callback_for_one_message_from_api_proxy()
            if self._is_new_list_tab_request:
                #print("{}: SENDING LIST TABS".format(self.in_fd))
                self._is_new_list_tab_request = False
                self._send_list_tabs_command(self.pid)
            else:
                print("Will read another chunk in a while")
        else:
            print("Not updated yet, cannot send another request")

    def async_create_tab(self, url):
        command = 'create_tab:%s;' % (url,)
        os.write(self._out_fd, command)

    def _send_list_tabs_command(self, pid):
        os.write(self._out_fd, 'list_tabs;')

    def _clean_fds(self):
        for fd in [self.in_fd, self.out_fd]:
            try:
                os.close(fd)
            except:
                pass

    def _activate_callback_for_one_message_from_api_proxy(self):
        self._nr_retries_left = 1000
        GLib.io_add_watch(self.in_fd, GLib.IO_IN, self._receive_message_from_api_proxy)
        GLib.timeout_add(50, self._receive_message_from_api_proxy)

    def _receive_message_from_api_proxy(self, *args, **kwargs):
        # Check if we got updated by the fd-based callback before the timer-tick-based callback
        if self._is_updated:
            return False

        self._nr_retries_left = max(0, self._nr_retries_left - 1)
        if self._nr_retries_left == 0:
            self._is_updated = True
            return False

        content = None
        try:
            content = self.read()
        except ApiProxyFdContentionTryAgainLater:
            print("scheduling another list tabs (self._is_updated stays False)")
        except Exception as ex:
            print(str(ex))
            print(type(ex))

        if content is not None:
            try:
                tabs = json.loads(content)
            except:
                print('cannot load content of size {}:'.format(len(content)))
                return

            self._update_tabs_callback(self.pid, tabs)
            self._is_updated = True

        whether_to_repeat = not self._is_updated
        return whether_to_repeat


class TabControl(object):
    def __init__(self, update_tabs_callback, update_tab_icon_callback):
        self._update_tabs_callback = update_tabs_callback
        self._update_tab_icon_callback = update_tab_icon_callback
        self.browsers = dict()

    def async_list_browsers_tabs(self, active_browsers):
        self._clean_stale_browsers(active_browsers)

        for browser in active_browsers:
            if self._validate_connection_to_browser(browser.pid):
                self.browsers[browser.pid].async_list_tabs()

    def async_move_to_tab(self, tab_id, pid):
        is_connected = self._validate_connection_to_browser(pid)
        if is_connected:
            self.browsers[pid].async_move_to_tab(tab_id)
        else:
            print("Warning: not connected to browser {}".format(pid))

    def _validate_connection_to_browser(self, pid):
        if pid not in self.browsers:
            try:
                browser = BrowserTabLister(pid, self._update_tabs_callback)
                self.browsers[pid] = browser
            except ApiProxyNotReady:
                return False
        return True

    def _clean_stale_browsers(self, active_browsers):
        active_browser_pids = set([browser.pid for browser in active_browsers])
        stale_browser_pids = [browser_pid for browser_pid in self.browsers.keys()
                              if browser_pid not in active_browser_pids]

        for browser in stale_browser_pids:
            browser._clean_fds()
            del self.browsers[browser.pid]
