import gi
import os
import signal
import subprocess
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gi.repository import Gtk, GdkX11, GLib
from utils import windowcontrol, window_entry, tabcontrol, glib_wrappers, bookmark_store
from gui import keycodes
from gui.components import entriestree, searchtextbox
from guiapps import entriessearch, chooseparentbookmarksdir, bookmarkssearch



class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"

    FULL_HELP_TEXT = ("Ctrl+J: Down\n"
                      "Ctrl+K: Up\n"
                      "Ctrl+W/U: Empty search filter\n"
                      "Ctrl+L: First (+reload)\n"
                      "Ctrl+D: Last\n"
                      "Ctrl+Backspace: SIGTERM selected\n"
                      "Ctrl+\\: SIGKILL selected\n"
                      "Ctrl+C: Hide\n"
                      "Ctrl+Space: Toggle expanded mode\n"
                      "Ctrl+H: Toggle Help")
    SHORT_HELP_TEXT = "Ctrl+H: Toggle Help"

    def __init__(self):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self._xid = None
        self._windows = {}
        self._tabs = {}
        self._bookmarks = []

        self._entriestree = entriestree.EntriesTree(self._entry_activated_callback,
                                                    self._treeview_keypress,
                                                    self._get_tab_icon_callback,
                                                    self._entry_selected_callback)
        self._status_label = self._create_status_label()
        self._bookmark_store = bookmark_store.BookmarksStore(self._list_bookmarks_callback,
                                                              self._connected_to_cloud_callback,
                                                              lambda: None)

        # Gui Apps (different modes for the same window layout)
        self._gui_apps = {'entries_search': entriessearch.EntriesSearch(self,
                                                          self._entriestree,
                                                          self._status_label,
                                                          self._bookmark_store),
                          'bookmarks_search': bookmarkssearch.BookmarksSearch(self,
                                                                              self._entriestree,
                                                                              self._status_label,
                                                                              self._bookmark_store),
                          'choose_parent_bookmarks_dir_app': chooseparentbookmarksdir.ChooseParentBookmarksDir(self,
                                                                                      self._entriestree,
                                                                                      self._status_label,
                                                                                      self._bookmark_store)
        }
        print("Switching to entries_search")
        self._current_app = self._gui_apps['entries_search']

        print("700")
        self._search_textbox = searchtextbox.SearchTextbox(self._handle_keypress,
                                                           self._entry_activated_callback,
                                                           self._entriestree,
                                                           )
        print("600")
        self._entriestree.select_first_window()
        print("500")
        self._tabcontrol = tabcontrol.TabControl(self._update_tabs_callback, self._tab_icon_ready)
        print("400")
        glib_wrappers.register_signal(self._focus_on_me, signal.SIGHUP)
        print("300")
        self._set_window_properties()
        print("200")
        self._help_label = self._create_help_label()

        print("100")
        self._add_gui_components_to_window()
        print("Listing windows...")
        self.async_list_windows()
        self.expanded_mode = True

    def _set_window_properties(self):
        self.set_size_request(500, 500)
        self.set_position(Gtk.WindowPosition.CENTER)

    def _add_gui_components_to_window(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)
        vbox.pack_start(self._search_textbox.element, expand=False, fill=True, padding=0)
        treeview_scroll_wrapper = self._create_treeview_scroll_wrapper()
        vbox.pack_start(treeview_scroll_wrapper, True, True, 0)
        vbox.pack_start(self._status_label, False, True, 0)
        vbox.pack_start(self._help_label, False, True, 0)

    def _create_treeview_scroll_wrapper(self):
        scrollable_treeview = Gtk.ScrolledWindow()
        scrollable_treeview.set_vexpand(True)
        scrollable_treeview.add(self._entriestree.treeview)
        return scrollable_treeview

    def _create_help_label(self):
        label = Gtk.Label()
        label.set_text(self.SHORT_HELP_TEXT)
        label.set_justify(Gtk.Justification.LEFT)
        return label

    def _create_status_label(self):
        label = Gtk.Label()
        label.set_text("Bookmarks: Connecting to drive")
        label.set_justify(Gtk.Justification.LEFT)
        return label

    def _focus_on_me(self):
        self.set_visible(True)
        windowcontrol.async_focus_on_window(self._get_xid())
        self.async_list_windows()

        self._search_textbox.element.set_text("")

    def _get_xid(self):
        if self._xid is None:
            try:
                self._xid = self.get_window().get_xid()
            except:
                # No XID yet
                raise
        return self._xid

    def _update_windows_listbox_callback(self, windows):
        windows = [window for window in windows if window.xid != self._get_xid()]
        self._windows = {window.xid: window_entry.WindowEntry(window, entriestree.ICON_SIZE) for window in windows}
        self._entriestree.refresh(self._windows, self._tabs, self._bookmarks, self.expanded_mode)
        self._async_list_tabs_from_windows_list(windows)

    def _tab_icon_ready(self, url, icon):
        # TODO can we refresh this tab list entry only
        self._entriestree.refresh(self._windows, self._tabs, self._bookmarks, self.expanded_mode)

    def enforce_expanded_mode(self):
        self._entriestree.enforce_expanded_mode(self.expanded_mode)

    def _async_list_tabs_from_windows_list(self, windows):
        active_browsers = [window for window in windows if window.is_browser()]
        active_browsers_pids = [browser.pid for browser in active_browsers]
        stale_browser_pids = [pid for pid in self._tabs if pid not in active_browsers_pids]
        for pid in stale_browser_pids:
            del self._tabs[pid]
        self._tabcontrol.async_list_browsers_tabs(active_browsers)

    def _update_tabs_callback(self, pid, tabs):
        self._tabs[pid] = tabs
        self._entriestree.refresh(self._windows, self._tabs, self._bookmarks, self.expanded_mode)

    def async_list_windows(self):
        windowcontrol.async_list_windows(callback=self._update_windows_listbox_callback)
        self._status_label.set_text("Bookmarks: Reading from drive...")
        self._bookmark_store.async_list_bookmarks()

    def select_last_item(self):
        cursor = self._entriestree.treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self._entriestree.treefilter)
            self._entriestree.treeview.set_cursor(nr_rows - 1)

    def select_next_item(self):
        model, _iter = self._entriestree.get_selected_row()
        row = model[_iter]
        if self.expanded_mode:
            try:
                next_row = row.iterchildren().next()
            except:
                next_row = row.next
        else:
            next_row = row.next
        while next_row is None and row is not None:
            next_row = row.next
            if next_row is None:
                row = row.parent
        if next_row is not None:
            self._entriestree.treeview.set_cursor(next_row.path)

    @staticmethod
    def _get_child_of_row(row):
        try:
            child = row.iterchildren().next()
        except StopIteration:
            child = None
        return child

    def select_previous_item(self):
        model, _iter = self._entriestree.get_selected_row()
        original = current = model[_iter]
        while current.previous is None and current.parent != None:
            current = current.parent
        if original == current and current.previous is not None:
            current = current.previous
            child = self._get_child_of_row(current)
            current_has_children = child is not None
            if current_has_children:
                current = child
                while True:
                    while current.next is not None:
                        current = current.next
                    child = self._get_child_of_row(current)
                    current_has_children = child is not None
                    if current_has_children:
                        current = current.child
                    else:
                        break
        self._entriestree.treeview.set_cursor(current.path)

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (keycodes.KEYCODE_ARROW_UP, keycodes.KEYCODE_ARROW_DOWN):
            self._search_textbox.element.grab_focus()

    def send_signal_to_selected_process(self, signal_type):
        window_id = self._entriestree.get_value_of_selected_row(entriestree.COL_NR_WINDOW_ID)
        window = self._windows[window_id]
        os.kill(window.get_pid(), signal_type)
        self.async_list_windows()

    def toggle_help_next(self):
        if self._help_label.get_text() == self.SHORT_HELP_TEXT:
            self._help_label.set_text(self.FULL_HELP_TEXT)
        else:
            self._help_label.set_text(self.SHORT_HELP_TEXT)

    def empty_search_textbox(self):
        self._search_textbox.element.set_text("")

    def _connected_to_cloud_callback(self):
        print("Connected to cloud")

    def _disconnected_from_cloud_callback(self):
        print("Disconnected from cloud")

    def _list_bookmarks_callback(self, bookmarks, is_connected):
        def update_bookmarks():
            self._bookmarks = bookmarks
            self._entriestree.refresh(self._windows, self._tabs, self._bookmarks, self.expanded_mode)
            if is_connected:
                self._status_label.set_text("Bookmarks: synced to drive")
            else:
                self._status_label.set_text("Bookmarks: Not connected, using local cache")
            return False

        GLib.timeout_add(0, update_bookmarks)

    def choose_parent_dir_for_adding_bookmark(self, name, url):
        self._switch_app("choose_parent_bookmarks_dir_app", name, url)

    def _switch_app(self, app_name, *args, **kwargs):
        print("Switching to {}".format(app_name))
        self._current_app = self._gui_apps[app_name]
        self._current_app.switch(*args, **kwargs)

    def _get_tab_icon_callback(self, tab):
        return self._tabcontrol.get_tab_icon(tab)

    def _entry_activated_callback(self, *_):
        self._current_app.handle_entry_activation()

    def _entry_selected_callback(self, *_):
        self._current_app.handle_entry_selection()

    def _handle_keypress(self, *args):
        self._current_app.handle_keypress(*args)
