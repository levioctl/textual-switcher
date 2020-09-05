import sys
import signal
from gui import keycodes
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkX11, GLib


class DefaultApp:
    def __init__(self, entries_datamodel, switcher_window, switch_app_func):
        self._entries_model = entries_datamodel
        self._switcher_window = switcher_window
        self._is_ctrl_pressed = False
        self._is_shift_pressed = False
        self._actions = {"Down": self._switcher_window.select_next_item,
                         "Up": self._switcher_window.select_previous_item,
                         "Escape"        : lambda: sys.exit(0),
                         "Ctrl+D"        : self._switcher_window.select_last_item,
                         "Ctrl+J"        : self._switcher_window.select_next_item,
                         "Ctrl+K"        : self._switcher_window.select_previous_item,
                         "Ctrl+C"        : lambda: self._switcher_window.set_visible(False),
                         "Ctrl+L"        : self._switcher_window.select_first_row,
                         "Ctrl+W"        : self._switcher_window.empty_search_textbox,
                         "Ctrl+Backspace": self._term_selected_process,
                         "Ctrl+Backslash": self._kill_selected_process,
                         "Ctrl+H"                       : self._switcher_window.toggle_help_text,
                         "Ctrl+R"                       : self._async_refresh_entries,
                         "Ctrl+Space"     : self._toggle_expanded_mode
        }
        self._switch_app = switch_app_func

    def switch(self):
        pass

    def _kill_selected_process(self):
        if self._is_ctrl_pressed:
            self._entries_model.send_signal_to_selected_process(signal.SIGKILL)

    def _term_selected_process(self):
        if self._is_ctrl_pressed:
            self._entries_model.send_signal_to_selected_process(signal.SIGTERM)

    def _toggle_expanded_mode(self):
        pass

    def _terminate(self):
        self._entries_model.send_signal_to_selected_process(signal.SIGTERM)

    def handle_keypress(self, keycode, is_ctrl_pressed, is_shift_pressed):
        keycode_textual_repr = keycodes.parse_keycode_to_textual_repr(keycode, is_ctrl_pressed, is_shift_pressed)

        if keycode_textual_repr in self._actions:
            action = self._actions[keycode_textual_repr]
            action()
        else:
            print(keycode_textual_repr, keycode)

    def handle_entry_activation(self):
        pass

    def handle_entry_selection(self):
        pass

    def _async_refresh_entries(self):
        self._entries_model.async_list_entries()
        self._switcher_window._status_label.set_text("Bookmarks: Reading from drive...")
