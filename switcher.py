import gi
import os
import sys
import signal
import subprocess
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository import Gtk, GdkX11
import pidfile
import listfilter
import tabcontrol
import glib_wrappers
import windowcontrol


KEYCODE_ESCAPE = 9
KEYCODE_CTRL = 37
KEYCODE_ARROW_DOWN = 116
KEYCODE_ARROW_UP = 111
KEYCODE_J = 44
KEYCODE_K = 45
KEYCODE_L = 46
KEYCODE_W = 25
KEYCODE_C = 54
KEYCODE_D = 40
KEYCODE_BACKSLASH = 22
KEYCODE_BACKSPACE = 54
KEYCODE_SPACE = 65


class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"
    _COL_NR_ICON, _COL_NR_WINDOW_TITLE, _COL_NR_PID, _COL_NR_WM_CLASS, _COL_NR_WINDOW_ID, _COL_NR_SEARCH_TOKEN = range(6)
    BROWSERS_WM_CLASSES = ["Navigator.Firefox"]

    def __init__(self):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self._xid = None
        self._search_textbox = self._create_search_textbox()
        self._tree = self._create_tree()
        self._treefilter = self._create_tree_filter()
        self._treeview = self._create_treeview()
        self._select_first_window()
        self._is_ctrl_pressed = False
        self._windowcontrol = windowcontrol.WindowControl()
        self._listfilter = listfilter.ListFilter()
        self._tabcontrol = tabcontrol.TabControl(self._update_tabs_callback)
        glib_wrappers.register_signal(self._focus_on_me, signal.SIGHUP)
        self._set_window_properties()
        self._add_gui_components_to_window()
        self._async_list_windows()
        self._windows = None
        self._tabs = dict()
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
        label = self._create_help_label()
        vbox.pack_start(label, False, True, 0)

    def _create_tree(self):
        tree = Gtk.TreeStore(Pixbuf, str, int, str, int, str)
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
                   self._COL_NR_WINDOW_TITLE: "Title"}
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

    @staticmethod
    def _create_help_label():
        label = Gtk.Label()
        label.set_text("Ctrl+J: Down\n"
                       "Ctrl+K: Up\n"
                       "Ctrl+W/U: Empty search filter\n"
                       "Ctrl+L: First (+reload)\n"
                       "Ctrl+D: Last\n"
                       "Ctrl+Backspace: SIGTERM selected\n"
                       "Ctrl+\\: SIGKILL selected\n"
                       "Ctrl+C: Hide")
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
        window_a_row = model[iter_a]
        title = window_a_row[self._COL_NR_WINDOW_TITLE]
        wm_class = window_a_row[self._COL_NR_WM_CLASS]
        window_a_score = self._get_score(title, wm_class)
        window_a_row = model[iter_b]
        title = window_a_row[self._COL_NR_WINDOW_TITLE]
        wm_class = window_a_row[self._COL_NR_WM_CLASS]
        window_b_score = self._get_score(title, wm_class)
        if window_a_score > window_b_score:
            return -1
        elif window_b_score > window_a_score:
            return 1
        return 0

    def _update_windows_listbox_callback(self, windows):
        self._windows = windows
        self._refresh_tree()

    def _refresh_tree(self):
        self._tree.clear()
        windows_other_than_me = [window for window in self._windows if window.xid != self._get_xid()]
        for window in self._windows:
            window_row_label = self._combine_title_and_wm_class(window.title, window.wm_class)
            token = window.title + ' '.join(tab['title'] for tab in self._tabs.get(window.pid, []))
            row_iter = self._tree.append(None, [window.icon, window_row_label, window.pid, window.wm_class, window.xid, token])
            if window.pid in self._tabs:
                for tab in self._tabs[window.pid]:
                    self._tree.append(row_iter, [window.icon, tab['title'], window.pid, None, window.xid, tab['title']])
        self._enforce_expanded_mode()
        self._select_first_window()
        self._async_list_tabs_from_windows_list(windows_other_than_me)

    def _enforce_expanded_mode(self):
        if self._expanded_mode:
            self._treeview.expand_all()
        else:
            self._treeview.collapse_all()

    def _async_list_tabs_from_windows_list(self, windows):
        active_browser_pids = [window.pid for window in windows if window.wm_class in self.BROWSERS_WM_CLASSES]
        stale_browser_pids = [pid for pid in self._tabs if pid not in active_browser_pids]
        for pid in stale_browser_pids:
            del self._tabs[pid]
        self._tabcontrol.async_list_browser_tabs(active_browser_pids)

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
        current = model[_iter]
        while current.previous is None and current.parent != None:
            current = current.parent
        if current.previous is not None:
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
        if keycode == KEYCODE_ARROW_DOWN:
            self._select_next_item()
        elif keycode == KEYCODE_ARROW_UP:
            self._select_previous_item()
        elif keycode == KEYCODE_CTRL:
            self._is_ctrl_pressed = True
        elif keycode == KEYCODE_ESCAPE:
            sys.exit(0)
        elif is_ctrl_pressed:
            if keycode == KEYCODE_D:
                self._select_last_item()
            if keycode == KEYCODE_J:
                self._select_next_item()
            elif keycode == KEYCODE_K:
                self._select_previous_item()
            elif keycode == KEYCODE_C:
                self.set_visible(False)
            elif keycode == KEYCODE_L:
                self._async_list_windows()
                self._select_first_window()
            elif keycode == KEYCODE_W:
                self._search_textbox.set_text("")
            elif keycode == KEYCODE_BACKSPACE:
                self._send_signal_to_selected_process(signal.SIGTERM)
            elif keycode == KEYCODE_BACKSLASH:
                self._send_signal_to_selected_process(signal.SIGKILL)
            elif keycode == KEYCODE_SPACE:
                self._expanded_mode = not self._expanded_mode
                self._enforce_expanded_mode()

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (KEYCODE_ARROW_UP, KEYCODE_ARROW_DOWN):
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

    def async_focus_on_window(self, window_id):
        self._windowcontrol.async_focus_on_window(window_id)

    def _text_changed_callback(self, search_textbox):
        # A bit of nasty GTK hackery
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
        # If row of selected window was found, choose the first tab (first child)
        if row != None:
            child_iter = model.iter_children(row.iter)
            if child_iter is not None:
                child_row = model[child_iter]
                self._treeview.set_cursor(child_row.path)

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
        title = row[self._COL_NR_SEARCH_TOKEN]
        wm_class = row[self._COL_NR_WM_CLASS]
        score = self._get_score(title, wm_class)
        return score > 30

    def _send_signal_to_selected_process(self, signal_type):
        pid = self._get_value_of_selected_row(self._COL_NR_PID)
        os.kill(pid, signal_type)
        self._async_list_windows()


def show_window(window):
    window.connect("delete-event", Gtk.main_quit)
    window.show_all()
    window.realize()


if __name__ == "__main__":
    # Not using an argument parser to not waste time in latency
    if len(sys.argv) != 2:
        print "Please specify the PID file as an argument"
        sys.exit(1)

    pid_filepath = sys.argv[1]
    pidfile.create(pid_filepath)

    window = EntryWindow()
    show_window(window)

    Gtk.main()
