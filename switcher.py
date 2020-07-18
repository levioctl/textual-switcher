import gi
import os
import sys
import signal
import subprocess
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gi.repository import Gtk, GdkX11
import pidfile
import listfilter
import tabcontrol
import glib_wrappers
import windowcontrol
import keycodes


class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"
    _COL_NR_ICON, _COL_NR_TITLE, _COL_NR_WINDOW_ID, _COL_NR_TAB_ID = range(4)
    ICON_SIZE = 25
    FULL_HELP_TEXT = ("Ctrl+J: Down\n"
                      "Ctrl+K: Up\n"
                      "Ctrl+W/U: Empty search filter\n"
                      "Ctrl+L: First (+reload)\n"
                      "Ctrl+D: Last\n"
                      "Ctrl+Backspace: SIGTERM selected\n"
                      "Ctrl+\\: SIGKILL selected\n"
                      "Ctrl+C: Hide\n"
                      "Ctrl+H: Toggle Help")
    SHORT_HELP_TEXT = "Ctrl+H: Toggle Help"

    def __init__(self):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self._xid = None
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
        self._help_label = self._create_help_label()
        self._add_gui_components_to_window()
        self._async_list_windows()
        self._windows = None
        self._tabs = {}
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
        vbox.pack_start(self._help_label, False, True, 0)

    def _create_tree(self):
        tree = Gtk.TreeStore(Pixbuf, str, int, int)
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

    def _combine_title_and_wm_class(self, window_title, wm_class):
        if wm_class is not None and wm_class:
            wm_class = wm_class.split(".")[-1]
            combined_title = "{} - {}".format(wm_class, window_title)
        else:
            combined_title = window_title
        return combined_title

    def _compare_windows(self, model, iter_a, iter_b, user_data):
        window_a = self._windows[model[iter_a][self._COL_NR_WINDOW_ID]]
        window_a_score = self._get_score(window_a.title, window_a.wm_class)
        window_b = self._windows[model[iter_b][self._COL_NR_WINDOW_ID]]
        window_b_score = self._get_score(window_b.title, window_b.wm_class)

        if window_a_score > window_b_score:
            return -1
        elif window_b_score > window_a_score:
            return 1
        return 0

    def _update_windows_listbox_callback(self, windows):
        windows = [window for window in windows if window.xid != self._get_xid()]
        self._windows = {window.xid: window for window in windows}
        self._refresh_tree()
        self._async_list_tabs_from_windows_list(windows)

    def _refresh_tree(self):
        self._tree.clear()
        for window in self._windows.values():
            window_row_label = self._combine_title_and_wm_class(window.title, window.wm_class)
            NON_TAB_FLAG = -1
            if window.icon is not None:
                window.icon = window.icon.scale_simple(self.ICON_SIZE, self.ICON_SIZE, InterpType.BILINEAR)
            row = [window.icon, window_row_label, window.xid, NON_TAB_FLAG]
            row_iter = self._tree.append(None, row)
            if window.is_browser():
                self._add_tabs_of_window_to_tree(window, row_iter)
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
                self._tree.append(row_iter, [icon, tab['title'], window.xid, tab['id']])

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
                window = self._windows[selected_window_id]
                window_score = self._get_score(window.title, window.wm_class)
                if best_score_so_far >= window_score:
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

    def _get_score(self, title, wm_class):
        score = self._listfilter.get_candidate_score(title)
        if wm_class is not None and wm_class:
            wm_class_score = self._listfilter.get_candidate_score(wm_class)
            score = max(score, wm_class_score)
        return score

    def _filter_window_list_by_search_key(self, model, _iter, data):
        row = model[_iter]
        window_id = row[self._COL_NR_WINDOW_ID]
        if window_id not in self._windows:
            return False
        title = row[self._COL_NR_TITLE]
        window = self._windows[window_id]
        token = title
        if isinstance(token, str):
            token = unicode(token, 'utf-8')
        tab_id = row[self._COL_NR_TAB_ID]
        is_tab = tab_id >= 0
        if window.pid in self._tabs:
            if window.is_browser() and not is_tab:
                tabs = self._tabs[window.pid]
                sep = unicode(' ', 'utf-8')
                token += sep.join(tab['title'] for tab in tabs)
            elif is_tab:
                matching = [tab for tab in self._tabs[window.pid] if tab['id'] == tab_id]
                if matching:
                    tab = matching[0]
                    token = tab['title']
        score = self._get_score(token, window.wm_class)
        return score > 30

    def _send_signal_to_selected_process(self, signal_type):
        window_id = self._get_value_of_selected_row(self._COL_NR_WINDOW_ID)
        window = self._windows[window_id]
        os.kill(window.pid, signal_type)
        self._async_list_windows()

    def _toggle_help_text(self):
        if self._help_label.get_text() == self.SHORT_HELP_TEXT:
            self._help_label.set_text(self.FULL_HELP_TEXT)
        else:
            self._help_label.set_text(self.SHORT_HELP_TEXT)


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
