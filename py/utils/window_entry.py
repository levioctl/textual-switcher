from gi.repository.GdkPixbuf import InterpType


class WindowEntry(object):
    def __init__(self, window, icon_size):
        self.window = window
        self.icon_size = icon_size
        if window.icon is not None:
            self.icon = window.icon.scale_simple(self.icon_size, self.icon_size, InterpType.BILINEAR)
        else:
            self.icon = None

    def get_label(self):
        if self.window.wm_class is not None and self.window.wm_class:
            wm_class = self.window.wm_class.split(".")[-1]
            combined_title = "{} - {}".format(self.window.wm_class, self.window.title)
        else:
            combined_title = title
        return combined_title

    def get_xid(self):
        return self.window.xid

    def get_pid(self):
        return self.window.pid

    def is_browser(self):
        return self.window.is_browser()
