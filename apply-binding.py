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
    cmd = ["dconf", "write", path, value]
    print "Setting {} to {}".format(path, value)
    subprocess.check_output(cmd)


def dconf_read(path):
    cmd = ["dconf", "read", path]
    output = subprocess.check_output(cmd)
    return output


def get_binding_list():
    bindings = dconf_read(BINDING_LIST_PATH)
    bindings = bindings.strip()
    if not bindings:
        return []
    bindings = bindings[bindings.index("["):] # Deal with '@as'
    bindings = bindings[1:-1]
    bindings = bindings.replace("'", "")
    bindings = bindings.split(",")
    bindings = [binding.strip() for binding in bindings if binding.strip()]
    return bindings


def does_binding_exist(name):
    bindings = get_binding_list()
    names = [binding.strip(" /").split("/")[-1] for binding in bindings]
    return name in names


def set_binding(cmd, key_combination, window_manager):
    new_binding_path = "{}/{}".format(CUSTOM_KEYB_PATH, BINDING_NAME)
    if does_binding_exist(BINDING_NAME):
        print "A key binding list-name entry already exists."
    else:
        bindings = get_binding_list()
        if window_manager in ('gnome', 'unity'):
            new_binding_path_with_slash = "{}/".format(new_binding_path)
            bindings.append(new_binding_path_with_slash)
        elif window_manager == 'cinnamon':
            bindings.append(new_binding_path)
        else:
            assert False, "invalid window manager"
        dconf_write(BINDING_LIST_PATH, str(bindings))

    print "Setting key bindings."
    binding_values = dict(name=BINDING_NAME,
                          binding=key_combination,
                          command=cmd)
    for name, value in binding_values.iteritems():
        binding_path = "{}/{}".format(new_binding_path, name)
        value = "'{}'".format(value)
        dconf_write(binding_path, value)


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


if __name__ == "__main__":
    args = parse_args()
    window_manager = detect_window_manager()
    if window_manager is None:
        print "Unsupported desktop environment: {}".format(wm)
        sys.exit(1)
    set_paths(window_manager)
    set_binding(args.command, args.key_combination, window_manager)
