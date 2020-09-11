import subprocess
from utils import windowcontrol
from guiapps import defaultapp
from gui import keycodes
from gui.components import entriestree


class EntriesSearch(defaultapp.DefaultApp):
    def __init__(self, *args, **kwrags):
        defaultapp.DefaultApp.__init__(self, *args, **kwrags)

    def handle_key_Ctrl_Backspace(self):
        """SIGTERM selected process"""
        self._term_selected_process()

    def handle_key_Ctrl_Backslash(self):
        """SIGKILL selected process"""
        self._kill_selected_process()

    def handle_entry_activation(self):
        window_id = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_ENTRY_ID_INT)
        if window_id is None:
            return
        windowcontrol.focus_on_window(window_id)
        # Setting the window to not visible causes Alt+Tab to avoid switcher (which is good)
        self._switcher_window.set_visible(False)
