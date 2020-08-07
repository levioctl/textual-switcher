import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk
from utils import windowcontrol


class SearchTextbox(object):
    def __init__(self, keypress_callback, entry_selected_callback, entriestree):
        self._entriestree = entriestree
        self.element = Gtk.Entry()
        self.element.set_text("")
        self.element.connect("changed", self._text_changed_callback)
        self.element.connect("key-press-event", keypress_callback)
        self.element.connect("activate", entry_selected_callback)

    def _text_changed_callback(self, search_textbox):
        search_key = search_textbox.get_text()
        search_key = search_key.decode('utf-8')
        self._entriestree.update_search_key(search_key)
        self._entriestree.enforce_expanded_mode(True)
        self._entriestree.treefilter.refilter()
        if not self._is_some_window_selected():
            self._entriestree.select_first_window()
        if len(self._entriestree.tree):
            self._entriestree.select_first_tab_under_selected_window()

    def _is_some_window_selected(self):
        _, _iter = self._entriestree.get_selected_row()
        return _iter is not None
