from guiapps import defaultapp


class TypeNameToRenameBookmarkEntry(defaultapp.DefaultApp):
    def __init__(self, *args, **kwargs):
        defaultapp.DefaultApp.__init__(self, *args, **kwargs)
        self._parent_dir_guid = None

    def switch(self, parent_dir_guid):
        self._parent_dir_guid = parent_dir_guid
        self._switcher_window._status_label.set_text("Type a new name for the selected entry and press Enter")

    def handle_entry_activation(self):
        new_name = self._switcher_window._search_textbox.element.get_text()
        self._entries_model._bookmark_store.rename(guid=self._parent_dir_guid,
                                                   new_name=new_name)
        self._switch_app("bookmarks_search")

    def handle_entry_selection(self):
        # Don't switch apps when selecting different entries, as we want to stay on this app, until the
        # user presses Enter (which is handled by handle_entry_activation).
        pass

