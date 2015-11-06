import os
import sys
import subprocess


BINDING_NAME = "textual-switcher"
CMD = "/usr/bin/python {}"
BINDING_LIST_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"


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
    bindings = bindings[1:-1]
    bindings = bindings.replace("'", "")
    bindings = bindings.split(",")
    bindings = [binding.strip() for binding in bindings]
    return bindings


def does_binding_exist(name):
    bindings = get_binding_list()
    names = [binding.strip(" /").split("/")[-1] for binding in bindings]
    return name in names


def set_binding(cmd, key_combination):
    if does_binding_exist(BINDING_NAME):
        print "A key binding already exists."
        return
    bindings = get_binding_list()
    new_binding_path = "{}/{}".format(BINDING_LIST_PATH, BINDING_NAME)
    new_binding_path_with_slash = "{}/".format(new_binding_path)
    bindings.append(new_binding_path_with_slash)
    dconf_write(BINDING_LIST_PATH, str(bindings))
    print "Setting key binding."
    binding_values = dict(name=BINDING_NAME,
                          binding=key_combination,
                          command=cmd)
    for name, value in binding_values.iteritems():
        binding_path = "{}/{}".format(new_binding_path, name)
        value = "'{}'".format(value)
        dconf_write(binding_path, value)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print "Usage: python {} script_path binding".format(__file__)
        print "Example binding: <Primary><Alt>w"
        print sys.argv
        sys.exit(1)
    script_path = sys.argv[1]
    if not os.path.exists(script_path):
        print "File in the given path does not exist."
        sys.exit(1)
    key_combination = sys.argv[2]
    cmd = CMD.format(script_path, key_combination)
    set_binding(cmd, key_combination)
