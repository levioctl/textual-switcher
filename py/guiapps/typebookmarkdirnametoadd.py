from guiapps import defaultapp


class TypeBookmarkDirnameToAdd(defaultapp.DefaultApp):
    def __init__(self, *args, **kwargs):
        defaultapp.DefaultApp.__init__(self, *args, **kwargs)
        self._parent_dir_guid = None

    def switch(self, parent_dir_guid):
        self._parent_dir_guid = parent_dir_guid
        self._switcher_window._status_label.set_text("Enter dir name in the textbox, and press enter.")

    def handle_entry_activation(self):
        folder_name = self._switcher_window._search_textbox.element.get_text()
        self._entries_model._bookmark_store.add_folder(parent_folder_guid=self._parent_dir_guid,
                                                       folder_name=folder_name)
        self._switch_app("bookmarks_search")

    def handle_entry_selection(self):
        # Don't switch apps when selecting different entries, as we want to stay on this app, until the
        # user presses Enter (which is handled by handle_entry_activation).
        pass
