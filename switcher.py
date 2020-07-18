import gi
import os
import sys
import signal
import subprocess
import yaml
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gi.repository import Gtk, GdkX11, GLib
import webbrowser
import pidfile
import listfilter
import tabcontrol
import glib_wrappers
import windowcontrol
import keycodes
import cloudfilesynchronizerthread
import window_entry


class BookmarksStore(object):
    BOOKMARKS_LOCAL_CACHE_FILENAME = os.path.expanduser("~/.config/textual-switcher/bookmarks.yaml")

    def __init__(self, list_bookmarks_main_glib_loop_callback):
        self._bookmarks = None
        self._list_bookmarks_main_glib_loop_callback = list_bookmarks_main_glib_loop_callback
        self._cloudfilesynchronizerthread = cloudfilesynchronizerthread.CloudFileSynchronizerThread(
                self.BOOKMARKS_LOCAL_CACHE_FILENAME,
                self._connected_to_cloud_callback,
                self._disconnected_from_cloud_callback,
                self._list_bookmarks_callback)

    def async_list_bookmarks(self):
        self._cloudfilesynchronizerthread.async_get_content()

        # For the first time, read bookmarks from local cache, if such exists
        if self._bookmarks is None:
            # TODO do it asynchronously
            with open(self.BOOKMARKS_LOCAL_CACHE_FILENAME) as bookmarks_file:
                self._bookmarks = yaml.safe_load(bookmarks_file)
            if self._bookmarks is None:
                self._bookmarks = []
            self._list_bookmarks_main_glib_loop_callback(self._bookmarks)

    def add_bookmark(self, url, title):
        assert self._bookmarks is not None
        self._bookmarks.append([url, title])
        bookmarks_local_path = self.BOOKMARKS_LOCAL_CACHE_FILENAME
        with open(bookmarks_local_path, "w") as local_bookmarks_file:
            yaml.safe_dump(self._bookmarks, local_bookmarks_file, encoding='utf-8', allow_unicode=True)
        
        self._cloudfilesynchronizerthread.async_write_to_cloud()

    def _list_bookmarks_callback(self, bookmarks_yaml):
        print("Bookmarks received from cloud.")
        self._bookmarks = yaml.safe_load(bookmarks_yaml)
        if self._bookmarks is None:
            self._bookmarks = []
        self._list_bookmarks_main_glib_loop_callback(self._bookmarks)

    def _connected_to_cloud_callback(self):
        pass

    def _disconnected_from_cloud_callback(self):
        pass


class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"

    RECORD_TYPE_WINDOW, RECORD_TYPE_BROWSER_TAB, RECORD_TYPE_BOOKMARKS_ROOT, RECORD_TYPE_BOOKMARK_ENTRY = range(4)
    _COL_NR_RECORD_TYPE, _COL_NR_ICON, _COL_NR_TITLE, _COL_NR_WINDOW_ID, _COL_NR_TAB_ID, _COL_NR_URL = range(6)
    ICON_SIZE = 25
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
        self._windows = dict()
        self._tabs = {}
        self._bookmarks = list()
        self._search_textbox = self._create_search_textbox()
        self._tree = self._create_tree()
        self._treefilter = self._create_tree_filter()
        self._treeview = self._create_treeview()
        self._select_first_window()
        self._windowcontrol = windowcontrol.WindowControl()
        self._listfilter = listfilter.ListFilter()
        self._tabcontrol = tabcontrol.TabControl(self._update_tabs_callback, self._tab_icon_ready)
        glib_wrappers.register_signal(self._focus_on_me, signal.SIGHUP)
        self._set_window_properties()
        self._bookmarks_store = BookmarksStore(self._list_bookmarks_callback)
        self._help_label = self._create_help_label()
        self._status_label = self._create_status_label()
        self._add_gui_components_to_window()
        self._async_list_windows()
        self._expanded_mode = True

    def _set_window_properties(self):
        self.set_size_request(500, 500)
        self.set_position(Gtk.WindowPosition.CENTER)

    def _add_gui_components_to_window(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)
        vbox.pack_start(self._search_textbox, expand=False, fill=True, padding=0)
        treeview_scroll_wrapper = self._create_treeview_scroll_wrapper()
        vbox.pack_start(treeview_scroll_wrapper, True, True, 0)
        vbox.pack_start(self._status_label, False, True, 0)
        vbox.pack_start(self._help_label, False, True, 0)

    def _create_tree(self):
        tree = Gtk.TreeStore(int, Pixbuf, str, int, int, str)
        tree.set_sort_func(1, self._compare_windows)
        tree.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        return tree

    def _create_search_textbox(self):
        search_textbox = Gtk.Entry()
        search_textbox.set_text("")
        search_textbox.connect("changed", self._text_changed_callback)
        search_textbox.connect("key-press-event", self._entry_keypress_callback)
        search_textbox.connect("activate", self._window_selected_callback)
        return search_textbox

    def _create_tree_filter(self):
        tree_filter = self._tree.filter_new()
        tree_filter.set_visible_func(self._filter_window_list_by_search_key)
        return tree_filter

    def _create_treeview(self):
        treeview = Gtk.TreeView.new_with_model(self._treefilter)
        treeview.set_headers_visible(False)
        treeview.connect("row-activated", self._window_selected_callback)
        treeview.connect("key-press-event", self._treeview_keypress)
        columns = {self._COL_NR_ICON: "Icon",
                   self._COL_NR_TITLE: "Title"}
        for i, column_title in columns.iteritems():
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == self._COL_NR_ICON:
                renderer = Gtk.CellRendererPixbuf()
                column = Gtk.TreeViewColumn(column_title, renderer, pixbuf=i)
            treeview.append_column(column)
        treeview.set_level_indentation(20)
        return treeview

    def _create_treeview_scroll_wrapper(self):
        scrollable_treeview = Gtk.ScrolledWindow()
        scrollable_treeview.set_vexpand(True)
        scrollable_treeview.add(self._treeview)
        return scrollable_treeview

    def _create_help_label(self):
        label = Gtk.Label()
        label.set_text(self.SHORT_HELP_TEXT)
        label.set_justify(Gtk.Justification.LEFT)
        return label

    def _create_status_label(self):
        label = Gtk.Label()
        label.set_text("Drive: not connected")
        label.set_justify(Gtk.Justification.LEFT)
        return label

    def _focus_on_me(self):
        self.set_visible(True)
        self._windowcontrol.async_focus_on_window(self._get_xid())
        self._async_list_windows()

        self._search_textbox.set_text("")

    def _get_xid(self):
        if self._xid is None:
            try:
                self._xid = self.get_window().get_xid()
            except:
                # No XID yet
                raise
        return self._xid

    def _compare_windows(self, model, iter_a, iter_b, user_data):
        record_a_type = model[iter_a][self._COL_NR_RECORD_TYPE]
        record_b_type = model[iter_b][self._COL_NR_RECORD_TYPE]
        if record_a_type != self.RECORD_TYPE_WINDOW:
            return -1
        if record_b_type != self.RECORD_TYPE_WINDOW:
            return 1

        window_a_id = model[iter_a][self._COL_NR_WINDOW_ID]
        window_b_id = model[iter_b][self._COL_NR_WINDOW_ID]

        if window_a_id == 0:
            return -1
        if window_b_id == 0:
            return 1

        window_a = self._windows[window_a_id]
        window_a_score = self._get_score(window_a.window.title, window_a.window.wm_class)
        window_b = self._windows[window_b_id]
        window_b_score = self._get_score(window_b.window.title, window_b.window.wm_class)

        if window_a_score > window_b_score:
            return -1
        elif window_b_score > window_a_score:
            return 1
        return 0

    def _update_windows_listbox_callback(self, windows):
        windows = [window for window in windows if window.xid != self._get_xid()]
        self._windows = {window.xid: window_entry.WindowEntry(window, self.ICON_SIZE) for window in windows}
        self._refresh_tree()
        self._async_list_tabs_from_windows_list(windows)

    def _refresh_tree(self):
        self._tree.clear()
        NON_TAB_FLAG = -1
        for window in self._windows.values():
            window_row_label = window.get_label()
            row = [self.RECORD_TYPE_WINDOW, window.icon, window.get_label(), window.get_xid(), NON_TAB_FLAG, None]
            row_iter = self._tree.append(None, row)

            if window.is_browser():
                self._add_tabs_of_window_to_tree(window, row_iter)


        # Add the bookmarks row
        icon = gi.repository.GdkPixbuf.Pixbuf.new_from_file("/usr/share/textual-switcher/4096584-favorite-star_113762.ico")
        #icon = icon.scale_simple(self.ICON_SIZE, self.ICON_SIZE, InterpType.BILINEAR)
        row = [self.RECORD_TYPE_BOOKMARKS_ROOT, icon, "Bookmarks", 0, NON_TAB_FLAG, None]
        row_iter = self._tree.append(None, row)
        for url, title in self._bookmarks:
            icon = gi.repository.GdkPixbuf.Pixbuf.new_from_file("/usr/share/textual-switcher/page_document_16748.ico")
            #icon = icon.scale_simple(self.ICON_SIZE, self.ICON_SIZE, InterpType.BILINEAR)
            label = u"{} ({})".format(title, url)
            self._tree.append(row_iter, [self.RECORD_TYPE_BOOKMARK_ENTRY, icon, label, 0, NON_TAB_FLAG, url])

        self._enforce_expanded_mode()
        self._select_first_window()

    def _add_tabs_of_window_to_tree(self, window, row_iter):
        if window.pid in self._tabs:
            for tab in self._tabs[window.pid]:
                icon = self._tabcontrol.get_tab_icon(tab)
                if icon is None:
                    icon = window.icon
                else:
                    icon = icon.scale_simple(self.ICON_SIZE, self.ICON_SIZE, InterpType.BILINEAR)
                self._tree.append(row_iter, [self.RECORD_TYPE_BROWSER_TAB, icon, tab['title'], window.get_xid(), tab['id'], tab['url']])

    def _tab_icon_ready(self, url, icon):
        self._refresh_tree()

    def _enforce_expanded_mode(self):
        if self._expanded_mode:
            self._treeview.expand_all()
        else:
            self._treeview.collapse_all()

    def _async_list_tabs_from_windows_list(self, windows):
        active_browsers = [window for window in windows if window.is_browser()]
        active_browsers_pids = [browser.pid for browser in active_browsers]
        stale_browser_pids = [pid for pid in self._tabs if pid not in active_browsers_pids]
        for pid in stale_browser_pids:
            del self._tabs[pid]
        self._tabcontrol.async_list_browsers_tabs(active_browsers)

    def _update_tabs_callback(self, pid, tabs):
        self._tabs[pid] = tabs
        self._refresh_tree()

    def _async_list_windows(self):
        self._windowcontrol.async_list_windows(callback=self._update_windows_listbox_callback)
        self._bookmarks_store.async_list_bookmarks()

    def _select_last_item(self):
        cursor = self._treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self._treefilter)
            self._treeview.set_cursor(nr_rows - 1)

    def _select_next_item(self):
        model, _iter = self._get_selected_row()
        row = model[_iter]
        if self._expanded_mode:
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
            self._treeview.set_cursor(next_row.path)

    @staticmethod
    def _get_child_of_row(row):
        try:
            child = row.iterchildren().next()
        except StopIteration:
            child = None
        return child

    def _select_previous_item(self):
        model, _iter = self._get_selected_row()
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
        self._treeview.set_cursor(current.path)

    def _entry_keypress_callback(self, *args):
        keycode = args[1].get_keycode()[1]
        state = args[1].get_state()
        is_ctrl_pressed = (state & state.CONTROL_MASK).bit_length() > 0
        # Don't switch focus in case of up/down arrow
        if keycode == keycodes.KEYCODE_ARROW_DOWN:
            self._select_next_item()
        elif keycode == keycodes.KEYCODE_ARROW_UP:
            self._select_previous_item()
        elif keycode == keycodes.KEYCODE_ESCAPE:
            sys.exit(0)
        elif is_ctrl_pressed:
            print(keycode)
            if keycode == keycodes.KEYCODE_D:
                self._select_last_item()
            if keycode == keycodes.KEYCODE_J:
                self._select_next_item()
            elif keycode == keycodes.KEYCODE_K:
                self._select_previous_item()
            elif keycode == keycodes.KEYCODE_C:
                self.set_visible(False)
            elif keycode == keycodes.KEYCODE_L:
                self._async_list_windows()
                self._select_first_window()
            elif keycode == keycodes.KEYCODE_W:
                self._search_textbox.set_text("")
            elif keycode == keycodes.KEYCODE_BACKSPACE:
                self._send_signal_to_selected_process(signal.SIGTERM)
            elif keycode == keycodes.KEYCODE_BACKSLASH:
                self._send_signal_to_selected_process(signal.SIGKILL)
            elif keycode == keycodes.KEYCODE_SPACE:
                self._expanded_mode = not self._expanded_mode
                self._enforce_expanded_mode()
            if keycode == keycodes.KEYCODE_H:
                self._toggle_help_text()
            if keycode == keycodes.KEYCODE_CTRL_PLUS:
                self._add_selection_as_bookmark()
            if keycode == keycodes.KEYCODE_CTRL_HYPEN:
                self._remove_selected_bookmark()

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (keycodes.KEYCODE_ARROW_UP, keycodes.KEYCODE_ARROW_DOWN):
            self._search_textbox.grab_focus()

    def _get_selected_row(self):
        selection = self._treeview.get_selection()
        return selection.get_selected()

    def _get_value_of_selected_row(self, col_nr):
        _filter, _iter = self._get_selected_row()
        if _iter is None:
            try:
                _iter = _filter.get_iter(0)
            except ValueError:
                # Nothing to select
                return None
        return _filter.get_value(_iter, col_nr)

    def _is_some_window_selected(self):
        _, _iter = self._get_selected_row()
        return _iter is not None

    def _window_selected_callback(self, *_):
        record_type = self._get_value_of_selected_row(self._COL_NR_RECORD_TYPE)
        if record_type in (self.RECORD_TYPE_BROWSER_TAB, self.RECORD_TYPE_WINDOW):
            window_id = self._get_value_of_selected_row(self._COL_NR_WINDOW_ID)
            if window_id is None:
                return
            try:
                self._windowcontrol.focus_on_window(window_id)
                # Setting the window to not visible causes Alt+Tab to avoid switcher (which is good)
                self.set_visible(False)
            except subprocess.CalledProcessError:
                # Actual window list has changed since last reload
                self._async_list_windows()
            tab_id = self._get_value_of_selected_row(self._COL_NR_TAB_ID)
            is_tab = tab_id >= 0
            if is_tab:
                window = self._windows[window_id]
                self._tabcontrol.async_move_to_tab(tab_id, window.pid)
        elif record_type == self.RECORD_TYPE_BOOKMARK_ENTRY:
            url = selected_window_id = self._get_value_of_selected_row(self._COL_NR_URL)
            webbrowser.open(url)

    def _text_changed_callback(self, search_textbox):
        search_key = search_textbox.get_text()
        self._listfilter.update_search_key(search_key)
        self._treefilter.refilter()
        if not self._is_some_window_selected():
            self._select_first_window()
        self._enforce_expanded_mode()
        if len(self._tree):
            self._select_first_tab_under_selected_window()

    def _select_first_tab_under_selected_window(self):
        # A bit of nasty GTK hackery
        # Find the selected row in the tree view model, using the window ID
        selected_window_id = self._get_value_of_selected_row(self._COL_NR_WINDOW_ID)
        #row = self._get_selected_row()
        model = self._treeview.get_model()
        _iter = model.get_iter_first()
        row = None
        while _iter is not None:
            row = model[_iter]
            if row[self._COL_NR_WINDOW_ID] == selected_window_id:
                break
            _iter = model.iter_next(_iter)

        # Select child row that best matches the search key (if matches more than the window row)
        if row != None:
            child_iter = model.iter_children(row.iter)
            best_row_so_far = None
            best_score_so_far = None
            while child_iter is not None:
                child_row = model[child_iter]
                child_title = child_row[self._COL_NR_TITLE]
                child_score = self._listfilter.get_candidate_score(child_title)
                #print((child_title, child_score))
                if best_row_so_far is None or child_score > best_score_so_far:
                    best_row_so_far = child_row
                    best_score_so_far = child_score
                child_iter = model.iter_next(child_iter)

            # Select the child row if better score than window
            if best_row_so_far is not None:

                is_window = self._get_value_of_selected_row(self._COL_NR_WINDOW_ID) == self.RECORD_TYPE_WINDOW
                if is_window:
                    window = self._windows[selected_window_id]
                    parent_score = self._get_score(window.title, window.wm_class)
                else:
                    title = self._get_value_of_selected_row(self._COL_NR_TITLE)
                    parent_score = self._get_score(title, "")

                if best_score_so_far >= parent_score:
                    # Selct tab
                    self._treeview.set_cursor(best_row_so_far.path)
                else:
                    # Select window
                    self._select_first_window()
            else:
                self._select_first_window()

    def _select_first_window(self):
        if len(self._tree):
            self._treeview.set_cursor(0)

    def _get_score(self, title, type_str):
        score = self._listfilter.get_candidate_score(title)
        if type_str is not None and type_str:
            type_str_score = self._listfilter.get_candidate_score(type_str)
            score = max(score, type_str_score)
        return score

    def _filter_window_list_by_search_key(self, model, _iter, data):
        row = model[_iter]
        record_type = row[self._COL_NR_RECORD_TYPE]

        type_str = ""
        token = row[self._COL_NR_TITLE].decode('utf-8')
        # Find token and type_str according to record type
        if record_type in (self.RECORD_TYPE_WINDOW, self.RECORD_TYPE_BROWSER_TAB):
            window_id = row[self._COL_NR_WINDOW_ID]
            if window_id is 0 or window_id not in self._windows:
                return False

            token = row[self._COL_NR_TITLE].decode('utf-8')
            window = self._windows[window_id]
            if window.get_pid() in self._tabs:
                tab_id = row[self._COL_NR_TAB_ID]
                is_tab = tab_id >= 0
                if window.is_browser() and not is_tab:
                    tabs = self._tabs[window.get_pid()]
                    sep = unicode(' ', 'utf-8')
                    token += sep.join(tab['title'] for tab in tabs)
                elif is_tab:
                    matching = [tab for tab in self._tabs[window.get_pid()] if tab['id'] == tab_id]
                    if matching:
                        tab = matching[0]
                        token = tab['title']

                type_str = window.wm_class.decode('utf-8')

        if isinstance(token, str):
            token = unicode(token, 'utf-8')

        score = self._get_score(token, type_str)
        return score > 30

    def _send_signal_to_selected_process(self, signal_type):
        window_id = self._get_value_of_selected_row(self._COL_NR_WINDOW_ID)
        window = self._windows[window_id]
        os.kill(window.get_pid(), signal_type)
        self._async_list_windows()

    def _toggle_help_text(self):
        if self._help_label.get_text() == self.SHORT_HELP_TEXT:
            self._help_label.set_text(self.FULL_HELP_TEXT)
        else:
            self._help_label.set_text(self.SHORT_HELP_TEXT)

    def _connected_to_cloud_callback(self):
        print("Connected to cloud")

    def _disconnected_from_cloud_callback(self):
        print("Disconnected from cloud")

    def _list_bookmarks_callback(self, bookmarks):
        def update_bookmarks():
            self._bookmarks = bookmarks
            self._refresh_tree()
            return False

        GLib.timeout_add(0, update_bookmarks)

    def _add_selection_as_bookmark(self):
        url = selected_window_id = self._get_value_of_selected_row(self._COL_NR_URL)
        title = selected_window_id = self._get_value_of_selected_row(self._COL_NR_TITLE)
        self._bookmarks_store.add_bookmark(url, title)


def show_window(window):
    window.connect("delete-event", Gtk.main_quit)
    window.show_all()
    window.realize()


if __name__ == "__main__":
    # Not using an argument parser to not waste time in latency
    if len(sys.argv) != 2:
        print("Please specify the PID file as an argument")
        sys.exit(1)

    pid_filepath = sys.argv[1]
    pidfile.create(pid_filepath)

    window = EntryWindow()
    show_window(window)

    Gtk.main()
