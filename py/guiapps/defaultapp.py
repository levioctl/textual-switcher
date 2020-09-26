import sys
import signal
from gui import keycodes
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkX11, GLib
from gui.components import entriestree


class DefaultApp:
    RECORD_TYPE_TO_APP = {entriestree.RECORD_TYPE_BOOKMARK_ENTRY: "bookmarks_search",
                          entriestree.RECORD_TYPE_BOOKMARKS_DIR: "bookmarks_search",
                          entriestree.RECORD_TYPE_WINDOW: "windows_search",
                          entriestree.RECORD_TYPE_BROWSER_TAB: "tabs_search"
    }

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

        does_binding_exist = hasattr(self, keycode_textual_repr)

        if does_binding_exist and self._should_binding_occur(keycode_textual_repr):
            action = getattr(self, keycode_textual_repr)
            action()
        else:
            # Print for debug
            print(keycode_textual_repr, keycode)

    def handle_entry_activation(self):
        pass

    def handle_entry_selection(self):
        # Use has move selection to a new row Switch the active app according to the row type
        record_type = self._switcher_window._entriestree.get_value_of_selected_row(entriestree.COL_NR_RECORD_TYPE)
        app_name = self.RECORD_TYPE_TO_APP[record_type]
        self._switch_app(app_name)

    def _should_binding_occur(self, method_name):
        should_binding_occur_method_name = "should_binding_occur_{}".format(method_name)
        should_binding_occur_method_exists = hasattr(self, should_binding_occur_method_name)

        if should_binding_occur_method_exists:
            should_binding_occur_method = getattr(self, should_binding_occur_method_name)
            result = should_binding_occur_method()
        else:
            result = True

        return result

    def _async_refresh_entries(self):
        self._entries_model.async_list_entries()
        self._switcher_window._status_label.set_text("Bookmarks: Reading from drive...")

    def _toggle_help_text(self):
        # Prepare a list of available methods to display (only those with docstring)
        methods = [method_name for method_name in dir(self) if 
                   method_name.startswith("handle_key_") and getattr(self, method_name).__doc__]

        # Filter only bindings that should occur
        methods = [method_name for method_name in methods if self._should_binding_occur(method_name)]

        # Put the default methods first, and the specialized (app-specific) methods later
        default_methods = [method_name for method_name in methods if hasattr(DefaultApp, method_name)]
        specialized_methods = [method for method in methods if method not in default_methods]

        def get_method_help_text(method, method_name):
            return "{}: {}".format(method_name[len("handle_key") + 1:]
                                   .replace("Backslash", "\\")
                                   .replace("Ctrl_", "Ctrl-"),
                                   method.__doc__)

        full_help_text = ""
        full_help_text += "\t" + "\n\t".join(get_method_help_text(getattr(self, method_name), method_name) for method_name in default_methods)
        full_help_text += "\n\n"
        full_help_text += "Binding for selected row type:\n\n"
        full_help_text += "\t" + "\n\t".join(get_method_help_text(getattr(self, method_name), method_name) for method_name in specialized_methods)

        # Display help text
        self._switcher_window.toggle_help_text(full_help_text)

    def handle_key_Down(self):
        self._switcher_window.select_next_item()

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

    def handle_key_Ctrl_H(self):
        """Toggle Help text"""
        self._toggle_help_text()

    def handle_key_Ctrl_R(self):
        """Refresh data"""
        self._async_refresh_entries()

    def handle_key_Ctrl_Space(self):
        """Toggle expanded mode"""
        self._toggle_expanded_mode()

    def handle_key_Ctrl_Q(self):
        """Authenticate drive connection"""
        self._entries_model.connect_to_drive_explicitly()

    def should_binding_occur_handle_key_Ctrl_Q(self):
        return self._entries_model.is_connected_to_drive()
