import os
import sys
import signal
import subprocess
import gi
gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gi.repository import Gtk, GdkX11, Wnck, GLib
import listfilter
import tabcontrol
import windowmanager


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

    def __init__(self, lockfile_path):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self.set_size_request(450, 500)
        self.set_position(Gtk.WindowPosition.CENTER)

        self._xid = None

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        self.entry = Gtk.Entry()
        self.entry.set_text("")
        self.entry.connect("changed", self._text_changed_callback)
        self.entry.connect("key-press-event", self._entry_keypress_callback)
        self.entry.connect("activate", self._entry_activated_callback)
        vbox.pack_start(self.entry, expand=False, fill=True, padding=0)

        self.task_liststore = Gtk.ListStore(Pixbuf, str, int, str, int)


        self.task_filter = self.task_liststore.filter_new()
        self.task_filter.set_visible_func(self._filter_window_list_by_search_key)

        self.treeview = Gtk.TreeView.new_with_model(self.task_filter)
        self.treeview.set_headers_visible(False)
        self.treeview.connect("row-activated", self._window_selected_callback)
        self.treeview.connect("key-press-event", self._treeview_keypress)
        columns = {self._COL_NR_ICON: "Icon",
                   self._COL_NR_WINDOW_TITLE: "Title"}
        for i, column_title in columns.iteritems():
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            if i == self._COL_NR_ICON:
                renderer = Gtk.CellRendererPixbuf()
                column = Gtk.TreeViewColumn(column_title, renderer, pixbuf=i)
            self.treeview.append_column(column)

        scrollable_treelist = Gtk.ScrolledWindow()
        scrollable_treelist.set_vexpand(True)
        scrollable_treelist.add(self.treeview)
        vbox.pack_start(scrollable_treelist, True, True, 0)
        self._select_first()
        self._is_ctrl_pressed = False

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
        self._wmcontrol = windowmanager.WindowManager(GLib)
        self._listfilter = listfilter.ListFilter()
        self._tabcontrol = tabcontrol.TabControl(GLib, self._update_tabs_callback)
        vbox.pack_start(label, False, True, 0)
        self._lockfile_path = lockfile_path
        self.register_sighup(self._focus_on_me)
        self._async_update_task_liststore()

    def _focus_on_me(self):
        self.set_visible(True)
        self._wmcontrol.async_focus_on_window(self._xid)
        self._async_update_task_liststore()
        self.entry.set_text("")

    def _get_icons(self):
        screen = Wnck.Screen.get_default()
        screen.force_update()
        icons = {w.get_xid(): w.get_icon() for w in screen.get_windows()}
        return icons

    def _update_xid(self):
        if self._xid is None:
            try:
                self._xid = self.get_window().get_xid()
                self._write_pid_file()
            except IOError:
                sys.exit(0)
            except:
                # No XID yet
                raise

    def _combine_title_and_wm_class(self, window_title, wm_class):
        if wm_class is not None and wm_class:
            wm_class = wm_class.split(".")[-1]
            combined_title = "{} - {}".format(wm_class, window_title)
        else:
            combined_title = window_title
        return combined_title

    def _get_window_at_index(self, index):
        title = self.task_liststore.get_value(self.task_liststore.get_iter(index), self._COL_NR_WINDOW_TITLE)
        wm_class = self.task_liststore.get_value(self.task_liststore.get_iter(index), self._COL_NR_WM_CLASS)
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

    def _update_task_liststore_callback(self, windows):
        self._update_xid()
        self.task_liststore.clear()
        icons = self._get_icons()
        windows_other_than_me = [window for window in windows if int(window[0], 16) != self._xid]
        for window_id_hex_str, pid, wm_class, window_title in windows_other_than_me:
            window_id = int(window_id_hex_str, 16)
            icon = icons.get(window_id, None)
            if icon is None:
                print 'No icon for window %d' % (window_id,)
                continue
            icon = icon.scale_simple(16, 16, InterpType.BILINEAR)
            window_row_label = self._combine_title_and_wm_class(window_title, wm_class)
            self.task_liststore.append([icon, window_row_label, pid, wm_class, window_id])
        self._select_first()
        self._async_list_tabs_from_windows_list(windows_other_than_me)

    def _async_list_tabs_from_windows_list(self, windows):
        active_browser_pids = [window[1] for window in windows if window[2] in self.BROWSERS_WM_CLASSES]
        self._tabcontrol.async_list_browser_tabs(active_browser_pids)

    def _update_tabs_callback(self, tabs):
        print tabs

    def _async_update_task_liststore(self):
        self._wmcontrol.async_list_windows(callback=self._update_task_liststore_callback)

    def _entry_activated_callback(self, *args):
        self._window_selected_callback()

    def _select_first_item(self):
        cursor = self.treeview.get_cursor()[0]
        if cursor is not None:
            self.treeview.set_cursor(0)
        return True

    def _select_last_item(self):
        cursor = self.treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self.task_filter)
            self.treeview.set_cursor(nr_rows - 1)
        return True

    def _select_next_item(self):
        cursor = self.treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self.task_filter)
            index = cursor.get_indices()[0]
            if index < nr_rows - 1:
                self.treeview.set_cursor(index + 1)
        return True

    def _select_previous_item(self):
        cursor = self.treeview.get_cursor()[0]
        if cursor is not None:
            index = cursor.get_indices()[0]
            if index > 0:
                self.treeview.set_cursor(index - 1)
        return True

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
                self._async_update_task_liststore()
                self._select_first()
            elif keycode == KEYCODE_W:
                self.entry.set_text("")
            elif keycode == KEYCODE_BACKSPACE:
                self._kill_selected_process("TERM")
            elif keycode == KEYCODE_BACKSLASH:
                self._kill_selected_process("KILL")

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (KEYCODE_ARROW_UP, KEYCODE_ARROW_DOWN):
            self.entry.grab_focus()
            return False

    def _get_value_of_selected_row(self, col_nr):
        selection = self.treeview.get_selection()
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
            self._wmcontrol.focus_on_window(window_id)
            self.set_visible(False)
        except subprocess.CalledProcessError:
            # Actual tasks list has changed since last reload
            self._async_update_task_liststore()
        self._select_first()

    def async_focus_on_window(self, window_id):
        self._wmcontrol.async_focus_on_window(window_id)

    def _text_changed_callback(self, entry):
        search_key = entry.get_text()
        self._listfilter.update_search_key(search_key)
        self.task_filter.refilter()
        self._sort_windows()
        self._select_first()

    def _sort_windows(self):
        order = range(len(self.task_liststore))
        order.sort(cmp=self._compare_windows)
        self.task_liststore.reorder(order)

    def _select_first(self):
        self.treeview.set_cursor(0)

    def _get_window_title_score(self, proc_title, wm_class):
        proc_title_score = self._listfilter.get_candidate_score(proc_title)
        wm_class_score = self._listfilter.get_candidate_score(wm_class)
        return max(proc_title_score, wm_class_score)

    def _filter_window_list_by_search_key(self, model, iter, data):
        proc_title = model[iter][self._COL_NR_WINDOW_TITLE]
        wm_class = model[iter][self._COL_NR_WM_CLASS]
        score = self._get_window_title_score(proc_title, wm_class)
        return score > 30

    def _write_pid_file(self):
        with open(self._lockfile_path, "wb") as f:
            pid = str(os.getpid())
            f.write(pid)

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
        self._async_update_task_liststore()


if __name__ == "__main__":
    # Not using an argument parser to not waste time in latency
    if len(sys.argv) != 2:
        print "Please specify the PID file as an argument"
        sys.exit(1)
    lockfile_path = sys.argv[1]
    win = EntryWindow(lockfile_path)
    win.connect("delete-event", Gtk.main_quit)
    win.show_all()
    win.realize()
    Gtk.main()
