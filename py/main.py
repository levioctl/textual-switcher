# To disaable annoying overlay (half-transparent scrollbar that appears only on mouse move)
import os
import sys
os.environ['GTK_OVERLAY_SCROLLING'] = "0"
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk
from utils import pidfile
from gui.components import entrieswindow
from datamodel import entries
from guiapps import entriessearch, chooseparentbookmarksdir, bookmarkssearch, tabssearch, typebookmarkdirnametoadd


class EntriesWindowController(entrieswindow.EntryWindow):
    def __init__(self, entries_datamodel, entries_window):
        self._entries_model = entries_datamodel
        self._entries_view = entries_window

        # Keyboard modes modes for the same window
        self._gui_apps = {'windows_search': entriessearch.EntriesSearch,
                          'bookmarks_search': bookmarkssearch.BookmarksSearch,
                          'choose_parent_bookmarks_dir_app': chooseparentbookmarksdir.ChooseParentBookmarksDir,
                          "tabs_search": tabssearch.TabsSearch,
                          "type_bookmark_dirname_to_add": typebookmarkdirnametoadd.TypeBookmarkDirnameToAdd
        }
        # Transform dict values (classes) to objects
        gui_apps_copy = dict(self._gui_apps)
        for gui_app_name, gui_app_class in self._gui_apps.iteritems():
            self._gui_apps[gui_app_name] = gui_app_class(self._entries_model, self._entries_view, self._switch_app)

        # Set startup app
        self._current_app = self._gui_apps['windows_search']

    def run(self):
        # Bind callbacks of GUI to updates from the data model
        self._entries_model.subscribe(
                list_windows_callback=self._entries_view.list_windows_callback,
                update_tabs_callback=self._entries_view.update_tabs_callback,
                list_bookmarks_callback=self._entries_view.list_bookmarks_callback,
        )
        self._entries_view.subscribe(keypress_callback=self._handle_keypress,
                                     focus_callback=self._focus_callback,
                                     entry_activated_callback=self._handle_entry_activation,
                                     entry_selected_callback=self._handle_entry_selection)

        # Refresh once
        self._current_app._async_refresh_entries()

        # Show window
        self._entries_view.show()

        # Run I/O loop
        self._entries_view.run()

    def _switch_app(self, app_name, *args, **kwargs):
        # Switch if we're not already on the needed app
        new_app_candidate = self._gui_apps[app_name]
        if self._current_app != new_app_candidate:
            self._current_app = self._gui_apps[app_name]
            self._current_app.switch(*args, **kwargs)

    def _handle_entry_activation(self):
        self._current_app.handle_entry_activation()

    def _handle_entry_selection(self):
        self._current_app.handle_entry_selection()

    def _handle_keypress(self, *args):
        self._current_app.handle_keypress(*args)

    def _focus_callback(self):
        self._current_app._async_refresh_entries()


if __name__ == "__main__":
    # Not using an argument parser to not waste time in latency
    if len(sys.argv) != 2:
        print("Please specify the PID file as an argument")
        sys.exit(1)

    pid_filepath = sys.argv[1]
    pidfile.create(pid_filepath)

    entries_datamodel = entries.Entries()
    entries_window = entrieswindow.EntryWindow()
    controller = EntriesWindowController(entries_datamodel=entries_datamodel, entries_window=entries_window)

    controller.run()
