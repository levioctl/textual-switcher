import os
import sys
import argparse
import subprocess


BINDING_NAME = "textual-switcher"
CUSTOM_KEYB_PATH = ""
BINDING_LIST_PATH = ""
DEFAULT_DESKTOP = "gnome"
SUPPORTED_WINDOW_MANAGERS = ['unity', 'gnome', 'cinnamon']

def set_paths(window_manager):
    global BINDING_LIST_PATH
    global CUSTOM_KEYB_PATH
    if window_manager == 'cinnamon':
        BINDING_LIST_PATH = "/org/cinnamon/desktop/keybindings/custom-list"
        CUSTOM_KEYB_PATH = "/org/cinnamon/desktop/keybindings/custom-keybindings"
    if window_manager in ('gnome', 'unity'):
        BINDING_LIST_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
        CUSTOM_KEYB_PATH = BINDING_LIST_PATH


def dconf_write(path, value):
    if isinstance(value, str):
        value = "'{}'".format(value)
    elif isinstance(value, list):
        value = str(value)
    cmd = ["dconf", "write", path, value]
    subprocess.check_output(cmd)


def dconf_read(path):
    cmd = ["dconf", "read", path]
    output = subprocess.check_output(cmd)
    return output


def get_binding_list():
    bindings = dconf_read(BINDING_LIST_PATH)
    bindings = bindings.strip().strip("'")
    if not bindings:
        return []
    bindings = bindings[bindings.index("["):] # Deal with '@as'
    bindings = bindings[1:-1]
    bindings = bindings.replace("'", "")
    bindings = bindings.split(",")
    bindings = [binding.strip() for binding in bindings if binding.strip()]
    return bindings


def add_binding_to_list_entry(new_binding_path, window_manager):
    if window_manager in ('gnome', 'unity'):
        entry_value = "{}/".format(new_binding_path)
    elif window_manager == 'cinnamon':
        entry_value = os.path.basename(new_binding_path)
    else:
        assert False, "invalid window manager"
    bindings = get_binding_list()
    if entry_value not in bindings:
        bindings.append(entry_value)
        dconf_write(BINDING_LIST_PATH, bindings)


def set_binding_entry(binding_values, entry_path, window_manager):
    for name, value in binding_values.iteritems():
        binding_path = "{}/{}".format(entry_path, name)
        dconf_write(binding_path, value)


def set_binding(cmd, key_combination, window_manager):
    entry_path = "{}/{}".format(CUSTOM_KEYB_PATH, BINDING_NAME)
    add_binding_to_list_entry(entry_path, window_manager)
    binding_values = dict(name=BINDING_NAME,
                          binding=key_combination,
                          command=cmd)
    set_binding_entry(binding_values, entry_path, window_manager)


def detect_window_manager():
    window_manager = os.getenv("XDG_CURRENT_DESKTOP", None)
    if window_manager is None:
        return None
    window_manager = window_manager.lower()
    if 'cinnamon' in window_manager:
        window_manager = 'cinnamon'
    if window_manager not in SUPPORTED_WINDOW_MANAGERS:
        return None
    return window_manager


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("key_combination")
    return parser.parse_args()


def canonize_binding(binding, window_manager):
    if window_manager in ('cinnamon',):
        binding = binding.replace('<Control>', '<Primary>')
        binding = [binding]
    return binding


if __name__ == "__main__":
    args = parse_args()
    window_manager = detect_window_manager()
    if window_manager is None:
        print "Unsupported desktop environment: {}".format(window_manager)
        sys.exit(1)
    key_combination = canonize_binding(args.key_combination, window_manager)
    set_paths(window_manager)
    set_binding(args.command, key_combination, window_manager)
