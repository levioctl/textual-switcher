import webbrowser
from gui import keycodes
from guiapps import defaultapp
from gui.components import entriestree


class BookmarksSearch(defaultapp.DefaultApp):
    def __init__(self, *args, **kwrags):
        defaultapp.DefaultApp.__init__(self, *args, **kwrags)

    def handle_key_Ctrl_Shift_N(self):
        """Create a bookmarks dir under selected dir"""
        guid = self._get_selected_bookmark_dir_guid()

        # Call switcher to add this as bookmark
        self._switch_app("type_bookmark_dirname_to_add", guid)

    def handle_key_Ctrl_I(self):
        """Rename selected entry"""
        guid = self._get_selected_bookmark_dir_guid()

        # Call switcher to add this as bookmark
        self._switch_app("type_name_to_rename_bookmark_entry", guid)

    def handle_key_Ctrl_Hyphen(self):
        """Remove selected bookmark from bookmarks"""
        self._remove_bookmark()

    def _get_selected_bookmark_dir_guid(self):
        # If selected entry is a URL, parent folder will be parent of selected entry.
        record_type = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        selected_entry_guid = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_STR)
        parent_folder_guid = None
        if record_type == entriestree.RECORD_TYPE_BOOKMARK_ENTRY:
            parent_folder = self._entries_model._bookmark_store.get_parent_of_entry(selected_entry_guid)
            parent_folder_guid = parent_folder['guid']
        # If selected entry is a folder, parent folder will be that folder
        elif record_type == entriestree.RECORD_TYPE_BOOKMARKS_DIR:
            parent_folder_guid = selected_entry_guid
        else:
            raise ValueError("Cannot add bookmark as selected entry is not a bookmark dir")
        return parent_folder_guid

    def handle_entry_activation(self):
        url = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_INFO_STR)
        print("Opening bookmark: {}".format(url))
        webbrowser.open(url)

    def _remove_bookmark(self):
        record_type = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        # Validate selection is a bookmark/dir entry
        if record_type not in (entriestree.RECORD_TYPE_BOOKMARK_ENTRY, entriestree.RECORD_TYPE_BOOKMARKS_DIR):
            raise RuntimeError("Cannot remove a non-bookmark entry")

        bookmark_id = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_STR)

        # Set status label to inform on bookmark removal attempt
        if record_type == entriestree.RECORD_TYPE_BOOKMARK_ENTRY:
            self._switcher_window._status_label.set_text("Removing bookmark...")
        elif record_type == entriestree.RECORD_TYPE_BOOKMARKS_DIR:
            self._switcher_window._status_label.set_text("Removing bookmark dir...")

        # Try remove bookmark
        try:
            self._entries_model._bookmark_store.remove(bookmark_id)
        except ValueError as ex:
            self._switcher_window._status_label.set_text(ex.message)
