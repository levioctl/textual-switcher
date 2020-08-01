import sys
import signal
from gui import keycodes


class DefaultApp:
    def __init__(self, switcher_window, _entriestree, status_textbox, _bookmark_store):
        self._switcher_window = switcher_window
        self._entriestree = _entriestree
        self._status_label = status_textbox
        self._bookmark_store = _bookmark_store
        self._actions = {True: {}, False: {}}
        self._is_ctrl_pressed = False

        self._actions[True][keycodes.KEYCODE_ARROW_DOWN] = self._switcher_window.select_next_item
        self._actions[True][keycodes.KEYCODE_ARROW_UP] = self._switcher_window.select_previous_item
        self._actions[False][keycodes.KEYCODE_ARROW_DOWN] = self._switcher_window.select_next_item
        self._actions[False][keycodes.KEYCODE_ARROW_UP] = self._switcher_window.select_previous_item
        self._actions[False][keycodes.KEYCODE_ESCAPE] = lambda: sys.exit(0)
        self._actions[True][keycodes.KEYCODE_D] = self._switcher_window.select_last_item
        self._actions[True][keycodes.KEYCODE_J] = self._switcher_window.select_next_item
        self._actions[True][keycodes.KEYCODE_K] = self._switcher_window.select_previous_item
        self._actions[True][keycodes.KEYCODE_C] = lambda: self._switcher_window.set_visible(False)
        self._actions[True][keycodes.KEYCODE_L] = self._refresh
        self._actions[True][keycodes.KEYCODE_W] = lambda: self._switcher_window.empty_search_textbox()
        self._actions[True][keycodes.KEYCODE_BACKSPACE] = self._term_selected_process
        self._actions[True][keycodes.KEYCODE_BACKSLASH] = self._kill_selected_process
        self._actions[True][keycodes.KEYCODE_H] = self._switcher_window.toggle_help_next
        self._actions[True][keycodes.KEYCODE_HYPEN] = None

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
        self._switcher_window.expanded_mode = not self._switcher_window.expanded_mode
        self._switcher_window.enforce_expanded_mode()

    def _terminate(self):
        self._switcher_window.send_signal_to_selected_process(signal.SIGTERM)

    def handle_keypress(self, *args):
        keycode = args[1].get_keycode()[1]
        print(keycode)
        state = args[1].get_state()
        self._is_ctrl_pressed = (state & state.CONTROL_MASK).bit_length() > 0
        # Don't switch focus in case of up/down arrow
        if keycode in self._actions[self._is_ctrl_pressed]:
            action = self._actions[self._is_ctrl_pressed][keycode]
            action()
