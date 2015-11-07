import sys
import socket
import subprocess
from gi.repository import Gtk, GdkX11, GObject


KEYCODE_ENTER = 36
KEYCODE_ARROW_DOWN = 116
KEYCODE_ARROW_UP = 111


class EntryWindow(Gtk.Window):
    WINDOW_TITLE = "Textual Switcher"

    def __init__(self):
        Gtk.Window.__init__(self, title="Textual Switcher")
        self.set_size_request(300, 300)

        self._xid = None
        self._normalized_search_key = ""

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        self.entry = Gtk.Entry()
        self.entry.set_text("Hello World")
        self.entry.connect("changed", self._text_changed)
        self.entry.connect("key-press-event", self._entry_keypress)
        self.entry.connect("activate", self._entry_activated)
        vbox.pack_start(self.entry, expand=False, fill=True, padding=0)

        self.task_liststore = Gtk.ListStore(str, str)
        self._update_task_liststore(is_first_time=True)

        self.task_filter = self.task_liststore.filter_new()
        self.task_filter.set_visible_func(self.task_filter_func)

        self.treeview = Gtk.TreeView.new_with_model(self.task_filter)
        self.treeview.connect("row-activated", self._window_selected)
        self.treeview.connect("key-press-event", self._treeview_keypress)
        for i, column_title in enumerate(["Task name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        scrollable_treelist = Gtk.ScrolledWindow()
        scrollable_treelist.set_vexpand(True)
        scrollable_treelist.add(self.treeview)
        vbox.pack_start(scrollable_treelist, True, True, 0)
        self._select_first()

    def _entry_set_focus(self, *args):
        print "focus"

    def _update_xid(self):
        if self._xid is None:
            try:
                self._xid = self.get_window().get_xid()
            except:
                # No XID yet
                pass

    def _update_task_liststore(self, is_first_time=False):
        self.task_liststore.clear()
        self._update_xid()
        task_list = self._get_windows_list()
        for window_id, window_title in task_list:
            print self._xid, window_id, window_title
            # Enforce only one instance
            if is_first_time and window_title == self.WINDOW_TITLE:
                print "Found another instance, exiting."
                self._focus_on_window(window_id)
                sys.exit(0)
            window_id_nr = int(window_id, 16)
            if self._xid != window_id_nr:
                self.task_liststore.append([window_title, window_id])

    def _entry_activated(self, *args):
        self._window_selected()

    def _entry_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        print keycode
        # Don't switch focus in case of up/down arrow
        if keycode == KEYCODE_ARROW_DOWN:
            cursor = self.treeview.get_cursor()[0]
            if cursor is not None:
                index = cursor.get_indices()[0]
                self.treeview.set_cursor(index + 1)
            return True
        elif keycode == KEYCODE_ARROW_UP:
            cursor = self.treeview.get_cursor()[0]
            if cursor is not None:
                index = cursor.get_indices()[0]
                self.treeview.set_cursor(index - 1)
            return True

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        print keycode
        if keycode not in (KEYCODE_ARROW_UP, KEYCODE_ARROW_DOWN):
            self.entry.grab_focus()
            return False

    def _check_window(self, w_id):
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
        window_id = _filter.get_value(_iter, 1)
        window_title = _filter.get_value(_iter, 0)
        # move the selected window to the current workspace
        #subprocess.check_call(["xdotool", "windowmove", "--sync", window_id, "100", "100"])
        # raise it (the command below alone should do the job, but sometimes fails
        # on firefox windows without first moving the window).
        print window_id, window_title
        self._focus_on_window(window_id)

    def _focus_on_window(self, window_id):
        cmd = ["wmctrl", "-iR", window_id]
        try:
            print cmd
            subprocess.check_call(cmd)
            sys.exit(0)
        except subprocess.CalledProcessError:
            # Actual tasks list has changed since last reload
            self._update_task_liststore()
            self._select_first()
            return

    def _get_windows_list(self):
        wlistOutput = subprocess.check_output(["wmctrl", "-l"])
        print wlistOutput
        wlist = [l.split(socket.gethostname()) for l in wlistOutput.splitlines()]
        wlist = [[wlist[i][0].split()[0], wlist[i][-1].strip()] for i, l in enumerate(wlist)]
        wlist = [w for w in wlist if self._check_window(w[0]) == True]
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
        proc_title = model[iter][0]
        normalized_proc_title = self._normalize(proc_title)
        if normalized_proc_title in self._normalized_search_key or \
            self._normalized_search_key in normalized_proc_title:
            return True
        return False

win = EntryWindow()
win.connect("delete-event", Gtk.main_quit)
win.show_all()
win.realize()
Gtk.main()
