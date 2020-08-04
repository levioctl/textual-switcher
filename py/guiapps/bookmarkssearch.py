from gui import keycodes
from guiapps import entriessearch
from gui.components import entriestree


class BookmarksSearch(entriessearch.EntriesSearch):
    def __init__(self, *args, **kwrags):
        entriessearch.EntriesSearch.__init__(self, *args, **kwrags)
        self._actions[keycodes.KEYCODE_CTRL_SHIFT_N] = self._add_folder

    def _add_folder(self):
        print("adding folder")

    def handle_entry_selection(self):
        record_type = self._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        if record_type in (entriestree.RECORD_TYPE_BROWSER_TAB, entriestree.RECORD_TYPE_WINDOW):
            self._switcher_window._switch_app("entries_search")
