import socket
import subprocess
from gi.repository import Gtk, GObject


class EntryWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="Entry Demo")
        self.set_size_request(200, 300)

        self._normalized_search_key = ""

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        self.entry = Gtk.Entry()
        self.entry.set_text("Hello World")
        self.entry.connect("changed", self._text_changed)
        vbox.pack_start(self.entry, True, True, 0)

        self.task_liststore = Gtk.ListStore(str)
        task_list = self._get_windows_list()
        for task_name in task_list:
            self.task_liststore.append([task_name])

        self.task_filter = self.task_liststore.filter_new()
        self.task_filter.set_visible_func(self.task_filter_func)

        self.treeview = Gtk.TreeView.new_with_model(self.task_filter)
        for i, column_title in enumerate(["Task name"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)

        scrollable_treelist = Gtk.ScrolledWindow()
        scrollable_treelist.set_vexpand(True)
        scrollable_treelist.add(self.treeview)
        vbox.pack_start(scrollable_treelist, True, True, 0)

    def _check_window(self, w_id):
        w_type = subprocess.check_output(["xprop", "-id", w_id])
        if " _NET_WM_WINDOW_TYPE_NORMAL" in w_type:
            return True
        else:
            return False

    def _get_windows_list(self):
        wlistOutput = subprocess.check_output(["wmctrl", "-l"])
        wlist = [l.split(socket.gethostname()) for l in wlistOutput.splitlines()]
        wlist = [[wlist[i][0].split()[0], wlist[i][-1].strip()] for i, l in enumerate(wlist)]
        wlist = [w[1] for w in wlist if self._check_window(w[0]) == True]
        return wlist

    def _text_changed(self, entry):
        search_key = entry.get_text()
        self._normalized_search_key = self._normalize(search_key)
        self.task_filter.refilter()

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
Gtk.main()
