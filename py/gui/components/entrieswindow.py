import gi
import os
import signal
import subprocess
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gi.repository import Gtk, GdkX11, GLib
from datamodel import entries
from utils import windowcontrol, glib_wrappers
from gui import keycodes
from gui.components import entriestree, searchtextbox
from gui import window_entry


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
        self._bookmarks = {}

        # Callbacks
        self._external_entry_selected_callback = None
        self._external_keypress_callback = None
        self._external_focus_callback = None
        self._external_entry_activated_callback = None

        self._entriestree = entriestree.EntriesTree(self._entry_activated_callback,
                                                    self._treeview_keypress,
                                                    self._entry_selected_callback)
        self._status_label = self._create_status_label()

        self._search_textbox = searchtextbox.SearchTextbox(self._keypress_callback,
                                                           self._text_changed_callback,
                                                           self._entry_activated_callback,
                                                           self._entriestree,
                                                           )
        self._entriestree.select_first_row()
        glib_wrappers.register_signal(self._focus_on_me, signal.SIGHUP)
        self._set_window_properties()
        self._help_label = self._create_help_label()

        self._add_gui_components_to_window()

    def subscribe(self, keypress_callback, focus_callback, entry_activated_callback, entry_selected_callback):
        self._external_keypress_callback = keypress_callback
        self._external_focus_callback = focus_callback
        self._external_entry_activated_callback = entry_activated_callback
        self._external_entry_selected_callback = entry_selected_callback

    def select_first_row(self):
        self._entriestree.select_first_row()

    def _keypress_callback(self, *args):
        keycode = args[1].get_keycode()[1]
        state = args[1].get_state()
        is_ctrl_pressed = (state & state.CONTROL_MASK).bit_length() > 0
        is_shift_pressed = (state & state.SHIFT_MASK).bit_length() > 0
        if self._external_keypress_callback is not None:
            self._external_keypress_callback(keycode, is_ctrl_pressed, is_shift_pressed)

    def set_window_score_func(self, get_window_score_func):
        self._entriestree.set_window_score_func(get_window_score_func)

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
        self._search_textbox.element.set_text("")
        self._external_focus_callback()

    def update_tabs_callback(self, pid, tabs):
        # Display tabs, first without icons
        self._entriestree.update_tabs(pid, tabs)

    def select_last_item(self):
        cursor = self._entriestree.treeview.get_cursor()[0]
        if cursor is not None:
            nr_rows = len(self._entriestree.treefilter)
            self._entriestree.treeview.set_cursor(nr_rows - 1)

    def select_next_item(self):
        # Get iterator to selected
        model, _iter = self._entriestree.get_selected_row()
        if _iter is None:
            return

        # Get next row
        row = model[_iter]
        if self._entriestree.expanded_mode:
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
                        #current = current.child
                        current = child
                    else:
                        break
        self._entriestree.treeview.set_cursor(current.path)

    def _treeview_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        if keycode not in (keycodes.KEYCODES["ARROW_UP"], keycodes.KEYCODES["ARROW_DOWN"]):
            self._search_textbox.element.grab_focus()

    def send_signal_to_selected_process(self, signal_type):
        window_id = self._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_INT)
        window = self._windows[window_id]
        os.kill(window.get_pid(), signal_type)
        self.async_list_windows()

    def toggle_help_text(self):
        if self._help_label.get_text() == self.SHORT_HELP_TEXT:
            self._help_label.set_text(self.FULL_HELP_TEXT)
        else:
            self._help_label.set_text(self.SHORT_HELP_TEXT)

    def empty_search_textbox(self):
        self._search_textbox.element.set_text("")

    def list_bookmarks_callback(self, bookmarks, is_connected):
        self._bookmarks = bookmarks

        def update_bookmarks():
            self._entriestree.update_bookmarks(self._bookmarks)

            if is_connected:
                self._status_label.set_text("Bookmarks: synced to drive")
            else:
                self._status_label.set_text("Bookmarks: Not connected, using local cache")
            return False

        GLib.timeout_add(0, update_bookmarks)

    def list_windows_callback(self, windows):
        # Remove own window listing
        if self._get_xid() is not None and self._get_xid() in self._windows:
            del self._windows[self._get_xid() ]

        # Update windows local cache
        self._windows = {window_xid: window_entry.WindowEntry(window, self._entriestree.ICON_SIZE)
            for window_xid, window in windows.iteritems()}

        # Refresh the treeview
        self._entriestree.update_windows(self._windows)

    def _entry_activated_callback(self, *_):
        if self._external_entry_activated_callback is not None:
            self._external_entry_activated_callback()

    def _entry_selected_callback(self, *_):
        if self._external_entry_selected_callback is not None:
            self._external_entry_selected_callback()

    def _text_changed_callback(self, search_key):
        self._entriestree.update_search_key(search_key)

    def _get_xid(self):
        if self._xid is None:
            try:
                self._xid = self.get_window().get_xid()
            except:
                # No XID yet
                raise
        return self._xid

    def show(self):
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()
        self.realize()

    def run(self):
        Gtk.main()
