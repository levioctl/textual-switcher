from guiapps import defaultapp
from gui.components import entriestree


class ChooseParentDirToMoveTo(defaultapp.DefaultApp):
    def __init__(self, *args, **kwrags):
        defaultapp.DefaultApp.__init__(self, *args, **kwrags)
        self._entry_guid = None

    def handle_entry_activation(self):
        print('activated')
        dest_parent_guid = self._get_selected_bookmark_dir_guid()
        self._entries_model._bookmark_store.move_entry(self._entry_guid, dest_parent_guid)
        self._switch_app("bookmarks_search")

    def _get_selected_bookmark_dir_guid(self):
        # If selected entry is a URL, parent folder will be parent of selected entry.
        record_type = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        selected_entry_guid = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_STR)
        parent_folder_guid = None
        if record_type == entriestree.RECORD_TYPE_BOOKMARK_ENTRY:
            print("Please select a bookmark dir, not an entry")
        # If selected entry is a folder, parent folder will be that folder
        elif record_type == entriestree.RECORD_TYPE_BOOKMARKS_DIR:
            parent_folder_guid = selected_entry_guid
        else:
            raise ValueError("Cannot add bookmark as selected entry is not a bookmark dir")
        return parent_folder_guid

    def switch(self, guid):
        self._entry_guid = guid
        self._switcher_window._status_label.set_text("Choose a new parent bookmark dir.")

    def handle_entry_selection(self):
        print('selected')
        # Don't switch apps when selecting different entries, as we want to stay on this app, until the
        # user presses Enter (which is handled by handle_entry_activation).
        pass
