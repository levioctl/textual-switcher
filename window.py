class Window(object):
    BROWSERS_WM_CLASSES = ["Navigator.Firefox", "google-chrome.Google-chrome"]

    def __init__(self):
        self.xid = None
        self.pid = None
        self.wm_class = None
        self.title = None
        self.destkop_id = None
        self.hostname = None

    def is_browser(self):
        return self.wm_class in self.BROWSERS_WM_CLASSES

