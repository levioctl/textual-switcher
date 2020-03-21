from gi.repository import GLib, Gio


def register_signal(callback, signal_type):
    def register_signal():
        GLib.idle_add(install_glib_handler, signal_type, priority=GLib.PRIORITY_HIGH)

    def handler(*args):
        signal_nr = args[0]
        if signal_nr == signal_type:
            callback()
            register_signal()

    def install_glib_handler(sig):
        unix_signal_add = None

        if hasattr(GLib, "unix_signal_add"):
            unix_signal_add = GLib.unix_signal_add
        elif hasattr(GLib, "unix_signal_add_full"):
            unix_signal_add = GLib.unix_signal_add_full

        if unix_signal_add is not None:
            unix_signal_add(GLib.PRIORITY_HIGH, sig, handler, sig)
        else:
            print("Can't install GLib signal handler; gi version is too old.")

    register_signal()


def async_run_subprocess(command):
    pid, stdin, stdout, _ = \
        GLib.spawn_async(command,
                         flags=GLib.SpawnFlags.SEARCH_PATH | GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                         standard_output=True,
                         standard_error=True)
    return stdout


def async_get_url(url, on_ready_callback):

    cancellable = Gio.Cancellable()

    def on_icon_ready_callback_wrapper(source_object, result, url):
        try:
            success, contents, etag = source_object.load_contents_finish(result)
        except GLib.GError as e:
            print("Error loading URL '%s': %s" % (url, e.message.decode('utf-8')))
        else:
            if success:
                on_ready_callback(url, contents)
            else:
                print("Error reading icon")
        finally:
            cancellable.reset()

    file_ = Gio.File.new_for_uri(url)
    file_.load_contents_async(cancellable, on_icon_ready_callback_wrapper, url)
