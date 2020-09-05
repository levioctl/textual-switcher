import webbrowser
from gui import keycodes
from guiapps import entriessearch
from gui.components import entriestree


class BookmarksSearch(entriessearch.EntriesSearch):
    def __init__(self, *args, **kwrags):
        entriessearch.EntriesSearch.__init__(self, *args, **kwrags)
        self._actions["Ctrl+Shift+N"] = self._add_folder

    def _add_folder(self):
        # Choose parent folder.

        # If selected entry is a URL, parent folder will be parent of selected entry.
        record_type = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        selected_entry_guid = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_STR)
        if record_type == entriestree.RECORD_TYPE_BOOKMARK_ENTRY:
            parent_folder = self._bookmark_store.get_parent_of_entry(selected_entry_guid)
            parent_folder_guid = parent_folder['guid']
        # If selected entry is a folder, parent folder will be that folder
        elif record_type == entriestree.RECORD_TYPE_BOOKMARKS_DIR:
            parent_folder_guid = selected_entry_guid

        self._bookmark_store.add_folder(parent_folder_guid=parent_folder_guid)

    def handle_entry_selection(self):
        record_type = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        if record_type in (entriestree.RECORD_TYPE_BROWSER_TAB, entriestree.RECORD_TYPE_WINDOW):
            self._switch_app("entries_search")

    def handle_entry_activation(self):
        url = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_STR)
        webbrowser.open(url)
