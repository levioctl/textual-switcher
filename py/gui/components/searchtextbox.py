import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk


class SearchTextbox(object):
    def __init__(self, keypress_callback, text_changed_callback, entry_selected_callback, entriestree):
        self._entriestree = entriestree
        self._text_changed_external_callback  = text_changed_callback
        self.element = Gtk.Entry()
        self.element.set_text("")
        self.element.connect("changed", self._text_changed_callback)
        self.element.connect("key-press-event", keypress_callback)
        self.element.connect("activate", entry_selected_callback)

    def _text_changed_callback(self, search_textbox):
        search_key = search_textbox.get_text()
        search_key = search_key.decode('utf-8')
        self._text_changed_external_callback(search_key)
