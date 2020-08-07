# To disaable annoying overlay (half-transparent scrollbar that appears only on mouse move)
import os
import sys
os.environ['GTK_OVERLAY_SCROLLING'] = "0"
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk
from utils import pidfile
from gui.components import entrieswindow


def show_window(window):
    window.connect("delete-event", Gtk.main_quit)
    window.show_all()
    window.realize()


if __name__ == "__main__":
    # Not using an argument parser to not waste time in latency
    if len(sys.argv) != 2:
        print("Please specify the PID file as an argument")
        sys.exit(1)

    pid_filepath = sys.argv[1]
    pidfile.create(pid_filepath)

    window = entrieswindow.EntryWindow()
    show_window(window)

    Gtk.main()
