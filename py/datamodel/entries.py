import gi
from gi.repository import Gtk
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from utils import bookmark_store, windowcontrol, tabcontrol


class Entries(object):
    def __init__(self):
        self._windows = {}
        self._bookmarks = []
        self._tabs = {}
        self._s = ""
        self._external_list_bookmarks_callback = None
        self._bookmark_store = None 
        self._external_update_tabs_callback = None
        self._tabcontrol = tabcontrol.TabControl(self._update_tabs_callback, None)

    def subscribe(self, list_windows_callback, update_tabs_callback, list_bookmarks_callback,
                  explicit_authentication_needed_callback):
        self._external_list_windows_callback = list_windows_callback
        self._external_update_tabs_callback = update_tabs_callback
        self._external_list_bookmarks_callback = list_bookmarks_callback
        self._external_explicit_authentication_needed_callback = explicit_authentication_needed_callback

        self._bookmark_store = bookmark_store.BookmarksStore(self._list_bookmarks_callback,
                                                             self._connected_to_cloud_callback,
                                                             lambda: None,
                                                             self._explicit_authentication_needed_callback)

    def connect_to_drive_explicitly(self):
        self._bookmark_store.connect_to_drive_explicitly()

    def is_connected_to_drive(self):
        return self._bookmark_store.is_connected_to_drive()

    def _list_bookmarks_callback(self, bookmarks, is_connected):
        self._bookmarks = bookmarks
        if self._external_list_bookmarks_callback is None:
            print("Bookmarks received but no subscribers to receive")
        else:
            self._external_list_bookmarks_callback(bookmarks, is_connected)

    def _connected_to_cloud_callback(self):
        print("Connected to cloud")

    def async_list_entries(self):
        windowcontrol.async_list_windows(callback=self._update_windows_listbox_callback)
        self._bookmark_store.async_list_bookmarks()

    def _update_windows_listbox_callback(self, windows):
        self._windows = {window.xid: window for window in windows}
        self._external_list_windows_callback(self._windows)
        self._async_list_tabs_from_windows_list(windows)

    def _async_list_tabs_from_windows_list(self, windows):
        active_browsers = [window for window in windows if window.is_browser()]
        active_browsers_pids = [browser.pid for browser in active_browsers]
        stale_browser_pids = [pid for pid in self._tabs if pid not in active_browsers_pids]
        for pid in stale_browser_pids:
            del self._tabs[pid]
        self._tabcontrol.async_list_browsers_tabs(active_browsers)

    def _update_tabs_callback(self, pid, tabs):
        self._tabs[pid] = tabs
        self._external_update_tabs_callback(pid, tabs)

    def _explicit_authentication_needed_callback(self):
        print("Entries: explicit auth. needed")
        self._external_explicit_authentication_needed_callback()
