import sys
import signal
from gui import keycodes
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkX11, GLib


class DefaultApp:
    def __init__(self, switcher_window, _entriestree, status_label, _bookmark_store):
        self._switcher_window = switcher_window
        self._entriestree = _entriestree
        self._status_label = status_label
        self._bookmark_store = _bookmark_store
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
                         keycodes.KEYCODE_CTRL_L        : self._refresh,
                         keycodes.KEYCODE_CTRL_W        : lambda: self._switcher_window.empty_search_textbox(),
                         keycodes.KEYCODE_CTRL_BACKSPACE: self._term_selected_process,
                         keycodes.KEYCODE_CTRL_BACKSLASH: self._kill_selected_process,
                         keycodes.KEYCODE_CTRL_H        : self._switcher_window.toggle_help_next,
                         keycodes.KEYCODE_CTRL_SPACE    : self._toggle_expanded_mode
        }

    def switch(self):
        pass

    def _kill_selected_process(self):
        if self._is_ctrl_pressed:
            self._switcher_window.send_signal_to_selected_process(signal.SIGKILL)

    def _term_selected_process(self):
        if self._is_ctrl_pressed:
            self._switcher_window.send_signal_to_selected_process(signal.SIGTERM)

    def _refresh(self):
        self._switcher_window.async_list_windows()
        self._entriestree.select_first_window()

    def _toggle_expanded_mode(self):
        pass

    def _terminate(self):
        self._switcher_window.send_signal_to_selected_process(signal.SIGTERM)

    def handle_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        state = args[1].get_state()
        self._is_ctrl_pressed = (state & state.CONTROL_MASK).bit_length() > 0
        self._is_shift_pressed = (state & state.SHIFT_MASK).bit_length() > 0
        keycode = (self._is_ctrl_pressed, self._is_shift_pressed, keycode)
        if keycode in self._actions:
            action = self._actions[keycode]
            action()

    def handle_entry_activation(self):
        pass

    def handle_entry_selection(self):
        pass
