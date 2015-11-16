import os
import re
import sys
import signal
import socket
import subprocess
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gi.repository import Gtk, GdkX11, GObject, Wnck, GLib


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


class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"
    _COL_NR_ICON, _COL_NR_WINDOW_TITLE, _COL_NR_WINDOW_ID = range(3)

    def __init__(self, initial_windows=None):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self.set_size_request(300, 300)

        self._xid = None
        self._normalized_search_key = ""

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        self.entry = Gtk.Entry()
        self.entry.set_text("")
        self.entry.connect("changed", self._text_changed)
        self.entry.connect("key-press-event", self._entry_keypress)
        self.entry.connect("key-release-event", self._entry_keyrelease)
        self.entry.connect("activate", self._entry_activated)
        vbox.pack_start(self.entry, expand=False, fill=True, padding=0)

        self.task_liststore = Gtk.ListStore(Pixbuf, str, int)


        self._update_task_liststore(initial_windows=initial_windows)

        self.task_filter = self.task_liststore.filter_new()
        self.task_filter.set_visible_func(self.task_filter_func)

        self.treeview = Gtk.TreeView.new_with_model(self.task_filter)
        self.treeview.set_headers_visible(False)
        self.treeview.connect("row-activated", self._window_selected)
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
        label.set_text("Keyboard shortcuts:\n"
                       "Ctrl+J: Move the selection down by one\n"
                       "Ctrl+K: Move the selection up by one\n"
                       "Ctrl+L: Reload the windows list\n"
                       "Ctrl+W: Empty search filter\n"
                       "Ctrl+C: Exit")
        label.set_justify(Gtk.Justification.LEFT)
        vbox.pack_start(label, False, True, 0)
        self.register_sighup(self._focus_on_me)

    def _focus_on_me(self):
        self._update_task_liststore()
        self._update_xid()
        self._focus_on_window(self._xid)

    def _get_icons(self):
        screen = Wnck.Screen.get_default()
        screen.force_update()
        icons = {w.get_xid(): w.get_icon() for w in screen.get_windows()}
        return icons

    def _update_xid(self):
        if self._xid is None:
            try:
                self._xid = self.get_window().get_xid()
                self._xid = int(self._xid, 16)
            except:
                # No XID yet
                pass

    def _update_task_liststore(self, initial_windows=None):
        self.task_liststore.clear()
        self._update_xid()
        if initial_windows is None:
            windows = self.get_windows()
        else:
            windows = initial_windows
        icons = self._get_icons()
        for window_id, window_title in windows:
            window_id_nr = int(window_id, 16)
            if self._xid == window_id_nr:
                continue
            icon = icons.get(window_id_nr, None)
            pixbuf = Gtk.IconTheme.get_default().load_icon("computer", 16, 0)
            icon = icon.scale_simple(16, 16, InterpType.BILINEAR)
            self.task_liststore.append([icon, window_title, window_id_nr])

    def _entry_activated(self, *args):
        self._window_selected()

    def _entry_keyrelease(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode == KEYCODE_CTRL:
            self._is_ctrl_pressed = False
        elif self._is_ctrl_pressed:
            if keycode == KEYCODE_C:
                    sys.exit(0)

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

    def _entry_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        # Don't switch focus in case of up/down arrow
        if keycode == KEYCODE_ARROW_DOWN:
            self._select_next_item()
        elif keycode == KEYCODE_ARROW_UP:
            self._select_previous_item()
        elif keycode == KEYCODE_CTRL:
            self._is_ctrl_pressed = True
        elif keycode == KEYCODE_ESCAPE:
            sys.exit(0)
        elif self._is_ctrl_pressed:
            if keycode == KEYCODE_J:
                self._select_next_item()
            elif keycode == KEYCODE_K:
                self._select_previous_item()
            elif keycode == KEYCODE_C:
                sys.exit(0)
            elif keycode == KEYCODE_L:
                self._update_task_liststore()
                self._select_first()
            elif keycode == KEYCODE_W:
                self.entry.set_text("")

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (KEYCODE_ARROW_UP, KEYCODE_ARROW_DOWN):
            self.entry.grab_focus()
            return False

    @classmethod
    def _check_window(cls, w_id):
        w_type = subprocess.check_output(["xprop", "-id", w_id])
        if " _NET_WM_WINDOW_TYPE_NORMAL" in w_type:
            return True
        else:
            return False

    def _window_selected(self, *_):
        selection = self.treeview.get_selection()
        _filter, _iter = selection.get_selected()
        if _iter is None:
            try:
                _iter = _filter.get_iter(0)
            except ValueError:
                # Nothing to select
                return
        window_id = _filter.get_value(_iter, self._COL_NR_WINDOW_ID)
        window_title = _filter.get_value(_iter, self._COL_NR_WINDOW_TITLE)
        # move the selected window to the current workspace
        #subprocess.check_call(["xdotool", "windowmove", "--sync", window_id, "100", "100"])
        # raise it (the command below alone should do the job, but sometimes fails
        # on firefox windows without first moving the window).
        try:
            self._focus_on_window(window_id)
        except subprocess.CalledProcessError:
            # Actual tasks list has changed since last reload
            self._update_task_liststore()
            self._select_first()

    @staticmethod
    def _focus_on_window(window_id):
        window_id = hex(window_id)
        cmd = ["wmctrl", "-iR", window_id]
        subprocess.check_call(cmd)

    @classmethod
    def get_windows(cls):
        wlistOutput = subprocess.check_output(["wmctrl", "-l"])
        wlist = [l.split(socket.gethostname()) for l in wlistOutput.splitlines()]
        wlist = [[wlist[i][0].split()[0], wlist[i][-1].strip()] for i, l in enumerate(wlist)]
        wlist = [w for w in wlist if cls._check_window(w[0]) == True]
        return wlist

    def _text_changed(self, entry):
        search_key = entry.get_text()
        self._normalized_search_key = self._normalize(search_key)
        self.task_filter.refilter()
        self._select_first()

    def _select_first(self):
        self.treeview.set_cursor(0)

    def _normalize(self, title):
        for c in [" ", "\n", "\t"]:
            title = title.replace(c, "")
        title = title.lower()
        return title

    def task_filter_func(self, model, iter, data):
        proc_title = model[iter][self._COL_NR_WINDOW_TITLE]
        normalized_proc_title = self._normalize(proc_title)
        if normalized_proc_title in self._normalized_search_key or \
            self._normalized_search_key in normalized_proc_title:
            return True
        return False

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

def validate_only_one_instance(windows):
    cmdline = "switcher.py"
    processes = subprocess.check_output(["ps", "aux"])
    matching = re.findall(".+\d.+python .*{}".format(__file__), processes)
    if matching:
        my_pid = os.getpid()
        for process in matching:
            parts = [item for item in process.split(" ") if item]
            pid = int(parts[1])
            if pid != my_pid:
                os.kill(pid, signal.SIGHUP)
                sys.exit(0)

windows = EntryWindow.get_windows()
validate_only_one_instance(windows)
win = EntryWindow(initial_windows=windows)
win.connect("delete-event", Gtk.main_quit)
win.show_all()
win.realize()
Gtk.main()
