import os.path
import yaml
import cloudfilesynchronizerthread


class NotConnectedToCloudStorage(Exception): pass


class BookmarksStore(object):
    (STATE_INITIALIZING,
     STATE_IDLE,
     STATE_WAITING_FOR_RESPONSE) = range(3)
    def __init__(self,
                 list_bookmarks_main_glib_loop_callback,
                 connected_to_cloud_callback,
                 disconnected_from_cloud_callback):
        self._bookmarks = None
        self._list_bookmarks_main_glib_loop_callback = list_bookmarks_main_glib_loop_callback
        self._cloudfilesynchronizerthread = cloudfilesynchronizerthread.CloudFileSynchronizerThread(
                "bookmarks.yaml",
                connected_to_cloud_callback,
                disconnected_from_cloud_callback,
                self._list_bookmarks_callback)

    def async_list_bookmarks(self):
        self._cloudfilesynchronizerthread.async_get_content()

    def add_bookmark(self, url, title):
        # Validate connection to cloud storage
        if self._bookmarks is None:
            raise NotConnectedToCloudStorage()

        # Write the local file (TODO do this asynchronously)
        self._bookmarks.append([url, title])
        with tempfile.NamedTemporaryFile() as local_bookmarks_file:
            yaml.safe_dump(self._bookmarks, local_bookmarks_file, encoding='utf-8', allow_unicode=True)
        
        # Write the file to cloud
        self._cloudfilesynchronizerthread.async_write_to_cloud()

    def _list_bookmarks_callback(self, bookmarks_yaml):
        print("Bookmarks received from cloud.")
        self._bookmarks = yaml.safe_load(bookmarks_yaml)
        if self._bookmarks is None:
            self._bookmarks = []
        self._list_bookmarks_main_glib_loop_callback(self._bookmarks)
