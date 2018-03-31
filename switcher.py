import gi
import sys
import signal
import subprocess
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
from gi.repository.GdkPixbuf import Pixbuf
from gi.repository import Gtk, GdkX11, GLib
import pidfile
import listfilter
import tabcontrol
import windowcontrol


KEYCODE_ESCAPE = 9
KEYCODE_ENTER = 36
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


class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"
    _COL_NR_ICON, _COL_NR_WINDOW_TITLE, _COL_NR_PID, _COL_NR_WM_CLASS, _COL_NR_WINDOW_ID = range(5)
    BROWSERS_WM_CLASSES = ["Navigator.Firefox"]

    def __init__(self):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self._xid = None
        self._search_textbox = self._create_search_textbox()
        self._windows_listbox = Gtk.ListStore(Pixbuf, str, int, str, int)
        self._list_filter = self._create_list_filter()
        self._treeview = self._create_treeview()
        self._select_first_window()
        self._is_ctrl_pressed = False
        self._windowcontrol = windowcontrol.WindowControl(GLib)
        self._listfilter = listfilter.ListFilter()
        self._tabcontrol = tabcontrol.TabControl(GLib, self._update_tabs_callback)
        self.register_sighup(self._focus_on_me)
        self._set_window_properties()
        self._add_gui_components_to_window()
        self._async_refresh_window_list()

    def _set_window_properties(self):
        self.set_size_request(450, 500)
        self.set_position(Gtk.WindowPosition.CENTER)

    def _add_gui_components_to_window(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)
        vbox.pack_start(self._search_textbox, expand=False, fill=True, padding=0)
        treeview_scroll_wrapper = self._create_treeview_scroll_wrapper()
        vbox.pack_start(treeview_scroll_wrapper, True, True, 0)
        label = self._create_help_label()
        vbox.pack_start(label, False, True, 0)

    def _create_search_textbox(self):
        search_textbox = Gtk.Entry()
        search_textbox.set_text("")
        search_textbox.connect("changed", self._text_changed_callback)
        search_textbox.connect("key-press-event", self._entry_keypress_callback)
        search_textbox.connect("activate", self._entry_activated_callback)
        return search_textbox

    def _create_list_filter(self):
        list_filter = self._windows_listbox.filter_new()
        list_filter.set_visible_func(self._filter_window_list_by_search_key)
        return list_filter

    def _create_treeview(self):
        treeview = Gtk.TreeView.new_with_model(self._list_filter)
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
        self._async_refresh_window_list()
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

    def _get_window_at_index(self, index):
        title = self._windows_listbox.get_value(self._windows_listbox.get_iter(index), self._COL_NR_WINDOW_TITLE)
        wm_class = self._windows_listbox.get_value(self._windows_listbox.get_iter(index), self._COL_NR_WM_CLASS)
        return title, wm_class

    def _compare_windows(self, window_a_index, window_b_index):
        title, wm_class = self._get_window_at_index(window_a_index)
        window_a_score = self._get_window_title_score(title, wm_class)
        title, wm_class = self._get_window_at_index(window_b_index)
        window_b_score = self._get_window_title_score(title, wm_class)
        if window_a_score > window_b_score:
            return -1
        elif window_b_score > window_a_score:
            return 1
        return 0

    def _update_windows_listbox_callback(self, windows):
        self._windows_listbox.clear()
        windows_other_than_me = [window for window in windows if window.xid != self._get_xid()]
        for window in windows:
            window_row_label = self._combine_title_and_wm_class(window.title, window.wm_class)
            self._windows_listbox.append([window.icon, window_row_label, window.pid, window.wm_class, window.xid])
        self._select_first_window()
        self._async_list_tabs_from_windows_list(windows_other_than_me)

    def _async_list_tabs_from_windows_list(self, windows):
        active_browser_pids = [window.pid for window in windows if window.wm_class in self.BROWSERS_WM_CLASSES]
        self._tabcontrol.async_list_browser_tabs(active_browser_pids)

    def _update_tabs_callback(self, tabs):
        print tabs

    def _async_refresh_window_list(self):
        self._windowcontrol.async_list_windows(callback=self._update_windows_listbox_callback)

    def _entry_activated_callback(self, *args):
        self._window_selected_callback()

    def _select_last_item(self):
        cursor = self._treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self._list_filter)
            self._treeview.set_cursor(nr_rows - 1)

    def _select_next_item(self):
        cursor = self._treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self._list_filter)
            index = cursor.get_indices()[0]
            if index < nr_rows - 1:
                self._treeview.set_cursor(index + 1)
            else:
                self._select_first_window()

    def _select_previous_item(self):
        cursor = self._treeview.get_cursor()[0]
        if cursor is not None:
            index = cursor.get_indices()[0]
            if index > 0:
                self._treeview.set_cursor(index - 1)
            else:
                self._select_last_item()

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
                self._async_refresh_window_list()
                self._select_first_window()
            elif keycode == KEYCODE_W:
                self._search_textbox.set_text("")
            elif keycode == KEYCODE_BACKSPACE:
                self._kill_selected_process("TERM")
            elif keycode == KEYCODE_BACKSLASH:
                self._kill_selected_process("KILL")

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (KEYCODE_ARROW_UP, KEYCODE_ARROW_DOWN):
            self._search_textbox.grab_focus()

    def _get_value_of_selected_row(self, col_nr):
        selection = self._treeview.get_selection()
        _filter, _iter = selection.get_selected()
        if _iter is None:
            try:
                _iter = _filter.get_iter(0)
            except ValueError:
                # Nothing to select
                return None
        return _filter.get_value(_iter, col_nr)

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
            self._async_refresh_window_list()

    def async_focus_on_window(self, window_id):
        self._windowcontrol.async_focus_on_window(window_id)

    def _text_changed_callback(self, search_textbox):
        search_key = search_textbox.get_text()
        self._listfilter.update_search_key(search_key)
        self._list_filter.refilter()
        self._sort_windows()

    def _sort_windows(self):
        order = range(len(self._windows_listbox))
        order.sort(cmp=self._compare_windows)
        self._windows_listbox.reorder(order)

    def _select_first_window(self):
        self._treeview.set_cursor(0)

    def _get_window_title_score(self, proc_title, wm_class):
        proc_title_score = self._listfilter.get_candidate_score(proc_title)
        wm_class_score = self._listfilter.get_candidate_score(wm_class)
        return max(proc_title_score, wm_class_score)

    def _filter_window_list_by_search_key(self, model, iter, data):
        proc_title = model[iter][self._COL_NR_WINDOW_TITLE]
        wm_class = model[iter][self._COL_NR_WM_CLASS]
        score = self._get_window_title_score(proc_title, wm_class)
        return score > 30

    def register_sighup(self, callback):
        def register_signal():
            GLib.idle_add(install_glib_handler, signal.SIGHUP, priority=GLib.PRIORITY_HIGH)

        def handler(*args):
            signal_nr = args[0]
            if signal_nr == signal.SIGHUP:
                callback()
                register_signal()

        def install_glib_handler(sig):
            unix_signal_add = None

            if hasattr(GLib, "unix_signal_add"):
                unix_signal_add = GLib.unix_signal_add
            elif hasattr(GLib, "unix_signal_add_full"):
                unix_signal_add = GLib.unix_signal_add_full

            if unix_signal_add:
                print("Register GLib signal handler: %r" % sig)
                unix_signal_add(GLib.PRIORITY_HIGH, sig, handler, sig)
            else:
                print("Can't install GLib signal handler, too old gi.")
        register_signal()

    def _kill_selected_process(self, signal):
        pid = self._get_value_of_selected_row(self._COL_NR_PID)
        params = ["kill", "-{}".format(signal), str(pid)]
        pid, stdin, stdout, _ = \
            GLib.spawn_async(
                params,
                flags=GLib.SpawnFlags.SEARCH_PATH|GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                standard_output=True,
                standard_error=True)
        self._async_refresh_window_list()


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
