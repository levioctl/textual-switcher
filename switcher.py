import os
import re
import sys
import signal
import socket
import threading
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
    _COL_NR_ICON, _COL_NR_WINDOW_TITLE, _COL_NR_WM_CLASS, _COL_NR_WINDOW_ID = range(4)

    def __init__(self, lockfile_path):
        Gtk.Window.__init__(self, title=self.WINDOW_TITLE)
        self.set_size_request(450, 500)
        self.set_position(Gtk.WindowPosition.CENTER)

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

        self.task_liststore = Gtk.ListStore(Pixbuf, str, str, int)


        self._async_update_task_liststore()

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
        self._lockfile_path = lockfile_path

    def on_focus(self, *args):
        if self.is_active():
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
                self._write_xid_file()
            except IOError:
                print "Cannot write XID file"
                sys.exit(0)
            except:
                # No XID yet
                pass

    def _combine_title_and_wm_class(self, window_title, wm_class):
        if wm_class:
            wm_class = wm_class.split(".")[-1]
            combined_title = "{} - {}".format(wm_class, window_title)
        else:
            combined_title = title
        return combined_title

    def _update_task_liststore_callback(self, windows):
        if not windows:
            return
        self._update_xid()
        self.task_liststore.clear()
        icons = self._get_icons()
        for window_id, wm_class, window_title in windows:
            window_id_nr = int(window_id, 16)
            if self._xid == window_id_nr:
                continue
            icon = icons.get(window_id_nr, None)
            if icon is None:
                continue
            pixbuf = Gtk.IconTheme.get_default().load_icon("computer", 16, 0)
            icon = icon.scale_simple(16, 16, InterpType.BILINEAR)
            window_title = self._combine_title_and_wm_class(window_title, wm_class)
            self.task_liststore.append([icon, window_title, wm_class, window_id_nr])
        self._select_first()

    def _async_update_task_liststore(self):
        params = ["wmctrl", "-lx"]
        pid, stdin, stdout, _ = GLib.spawn_async(params,
            flags=GLib.SpawnFlags.SEARCH_PATH|GLib.SpawnFlags.DO_NOT_REAP_CHILD,                                       
            standard_output=True,
            standard_error=True)
        io = GLib.IOChannel(stdout)

        def parse_wlist_output(wlist_output):
            windows = list()
            for line in wlist_output.splitlines():
                xid, line = line.split(" ", 1)
                line = line.lstrip()
                desktop_id, line = line.split(" ", 1)
                del desktop_id
                line = line.lstrip()
                wm_class, line = line.split(" ", 1)
                if wm_class == "N/A":
                    continue
                line = line.lstrip()
                hostname, line = line.split(" ", 1)
                del hostname
                title = line.lstrip()
                window = [xid, wm_class, title]
                windows.append(window)
            return windows

        def wlist_finish_callback(*args, **kwargs):
            wlist_output = io.read()
            windows = parse_wlist_output(wlist_output)
            self._update_task_liststore_callback(windows)

        self.source_id_out = io.add_watch(GLib.IO_IN|GLib.IO_HUP,
                                          wlist_finish_callback,
                                          priority=GLib.PRIORITY_HIGH)

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
                self._async_update_task_liststore()
                self._select_first()
            elif keycode == KEYCODE_W:
                self.entry.set_text("")

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (KEYCODE_ARROW_UP, KEYCODE_ARROW_DOWN):
            self.entry.grab_focus()
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
            self.focus_on_window(window_id)
        except subprocess.CalledProcessError:
            # Actual tasks list has changed since last reload
            self._async_update_task_liststore()
        self._select_first()

    @staticmethod
    def focus_on_window(window_id):
        window_id = hex(window_id)
        cmd = ["wmctrl", "-iR", window_id]
        subprocess.check_call(cmd)

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
        wm_class = model[iter][self._COL_NR_WM_CLASS]
        normalized_wm_class = self._normalize(wm_class)
        if wm_class in self._normalized_search_key or \
            self._normalized_search_key in normalized_wm_class:
            return True
        return False

    def _write_xid_file(self):
        with open(self._lockfile_path, "wb") as f:
            xidHex = "0x%08x" % (self._xid,)
            f.write(xidHex)


lockfile_path = sys.argv[1]
win = EntryWindow(lockfile_path)
win.connect("delete-event", Gtk.main_quit)
win.connect('notify::is-active', win.on_focus)
win.show_all()
win.realize()
Gtk.main()
