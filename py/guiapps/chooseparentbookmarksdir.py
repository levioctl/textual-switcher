from guiapps import defaultapp


class ChooseParentBookmarksDir(defaultapp.DefaultApp):
    def __init__(self, *args, **kwargs):
        defaultapp.DefaultApp.__init__(self, *args, **kwargs)
        self._name = None
        self._url = None

    def switch(self, name, url):
        self._bookmark_name = name
        self._bookmark_url = url
        self._status_label.set_text("Choose a parent bookmark dir")

    def handle_entry_selection(self, *_):
        parent_dir_entry_id = self._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_INFO_STR)
        print("Adding bookmark...")
        self._bookmark_store.add_bookmark(self._bookmark_url, self._bookmark_name, parent_dir_entry_id)
        self._switcher_window._switch_app("entries_search")

