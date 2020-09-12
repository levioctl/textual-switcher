from guiapps import defaultapp
from gui.components import entriestree


class ChooseParentBookmarksDir(defaultapp.DefaultApp):
    def __init__(self, *args, **kwargs):
        defaultapp.DefaultApp.__init__(self, *args, **kwargs)
        self._name = None
        self._url = None

    def switch(self, name, url):
        self._bookmark_name = name
        self._bookmark_url = url
        self._switcher_window._status_label.set_text("Choose a parent bookmark dir")

    def handle_entry_activation(self, *_):
        parent_dir_entry_id = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_STR)
        print("Adding bookmark...")
        self._switcher_window._status_label.set_text("Adding bookmark...")
        self._entries_model._bookmark_store.add_bookmark(self._bookmark_url, self._bookmark_name, parent_dir_entry_id)
        self._switch_app("bookmarks_search")

    def handle_entry_selection(self):
        # Don't switch apps when selecting different entries, as we want to stay on this app, until the
        # user presses Enter (which is handled by handle_entry_activation).
        pass
