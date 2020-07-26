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
                self._list_bookmarks_callback,
                self._get_local_cache_callback)

    def async_list_bookmarks(self):
        if self._bookmarks is None:
            self._cloudfilesynchronizerthread.async_read_local_cache()
        self._cloudfilesynchronizerthread.async_read()

    def add_bookmark(self, url, title):
        # Validate connection to cloud storage
        if self._bookmarks is None:
            raise NotConnectedToCloudStorage()

        # Write the local file (TODO do this asynchronously)
        self._bookmarks.append([url, title])
        contents = yaml.dump(self._bookmarks, encoding='utf-8', allow_unicode=True)
        
        # Write the file to cloud
        self._cloudfilesynchronizerthread.async_write(contents)

    def _list_bookmarks_callback(self, bookmarks_yaml):
        print("Bookmarks received from cloud.")
        self._update_bookmarks_from_encoded_yaml(bookmarks_yaml)

    def _get_local_cache_callback(self, bookmarks_yaml_cache):
        if self._bookmarks is None:
            print("Bookmarks read from local cache.")
            self._update_bookmarks_from_encoded_yaml(bookmarks_yaml_cache)
        else:
            print("Bookmarks read from local cache, but local cache is not empty.")

    def _update_bookmarks_from_encoded_yaml(self, encoded_yaml):
        self._bookmarks = yaml.safe_load(encoded_yaml)
        if self._bookmarks is None:
            self._bookmarks = []
    
        self._list_bookmarks_main_glib_loop_callback(self._bookmarks)
