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
        keycode_textual_repr = "handle_key_" + keycodes.parse_keycode_to_textual_repr(keycode, is_ctrl_pressed, is_shift_pressed)

        if hasattr(self, keycode_textual_repr):
            action = getattr(self, keycode_textual_repr)
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

    def _toggle_help_text(self):
        methods = [method_name for method_name in dir(self) if 
                   method_name.startswith("handle_key_")]
        full_help_text = "\n".join("{}: {}".format(method_name[len("handle_key") + 1:].replace("Backslash", "\\"),
                                                   getattr(self, method_name).__doc__)
                                   for method_name in methods
                                   if getattr(self, method_name).__doc__ is not None)
        self._switcher_window.toggle_help_text(full_help_text)

    def handle_key_Down(self):
        self._switcher_window.select_next_item,

    def handle_key_Up(self):
        self._switcher_window.select_previous_item()

    def handle_key_Escape(self):
        """Quit"""
        sys.exit(0)

    def handle_key_Ctrl_D(self):
        """Select last row"""
        self._switcher_window.select_last_item()

    def handle_key_Ctrl_J(self):
        """Select next row"""
        self._switcher_window.select_next_item()

    def handle_key_Ctrl_K(self):
        """Select previous row"""
        self._switcher_window.select_previous_item()

    def handle_key_Ctrl_C(self):
        """Hide"""
        self._switcher_window.set_visible(False)

    def handle_key_Ctrl_L(self):
        """Select first row"""
        self._switcher_window.select_first_row()

    def handle_key_Ctrl_W(self):
        """Empty search box"""
        self._switcher_window.empty_search_textbox()

    def handle_key_Ctrl_Backspace(self):
        """SIGTERM selected process"""
        self._term_selected_process()

    def handle_key_Ctrl_Backslash(self):
        """SIGKILL selected process"""
        self._kill_selected_process()

    def handle_key_Ctrl_H(self):
        """Toggle Help text"""
        self._toggle_help_text()

    def handle_key_Ctrl_R(self):
        """Refresh data"""
        self._async_refresh_entries()

    def handle_key_Ctrl_Space(self):
        """Toggle expanded mode"""
        self._toggle_expanded_mode()
