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
        self._actions = {keycodes.KEYCODE_ARROW_DOWN    : self._switcher_window.select_next_item,
                         keycodes.KEYCODE_ARROW_UP      : self._switcher_window.select_previous_item,
                         keycodes.KEYCODE_ARROW_DOWN    : self._switcher_window.select_next_item,
                         keycodes.KEYCODE_ARROW_UP      : self._switcher_window.select_previous_item,
                         keycodes.KEYCODE_ESCAPE        : lambda: sys.exit(0),
                         keycodes.KEYCODE_CTRL_D        : self._switcher_window.select_last_item,
                         keycodes.KEYCODE_CTRL_J        : self._switcher_window.select_next_item,
                         keycodes.KEYCODE_CTRL_K        : self._switcher_window.select_previous_item,
                         keycodes.KEYCODE_CTRL_C        : lambda: self._switcher_window.set_visible(False),
                         keycodes.KEYCODE_CTRL_L        : self._switcher_window.select_first_window,
                         keycodes.KEYCODE_CTRL_W        : self._switcher_window.empty_search_textbox,
                         keycodes.KEYCODE_CTRL_BACKSPACE: self._term_selected_process,
                         keycodes.KEYCODE_CTRL_BACKSLASH: self._kill_selected_process,
                         keycodes.KEYCODE_CTRL_H        : self._switcher_window.toggle_help_text,
                         keycodes.KEYCODE_CTRL_R        : self._async_refresh_entries,
                         keycodes.KEYCODE_CTRL_SPACE    : self._toggle_expanded_mode
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
        keycode = (is_ctrl_pressed, is_shift_pressed, keycode)
        print(keycode)
        if keycode in self._actions:
            action = self._actions[keycode]
            action()

    def handle_entry_activation(self):
        pass

    def handle_entry_selection(self):
        pass

    def _async_refresh_entries(self):
        print("Clearing...")
        self._entries_model.async_list_entries()
        self._switcher_window._status_label.set_text("Bookmarks: Reading from drive...")
