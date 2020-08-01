import uuid
import os.path
import yaml
import traceback
import cloudfilesynchronizerthread


class NotConnectedToCloudStorage(Exception): pass


class BookmarksStore(object):
    (STATE_IDLE,
     STATE_WAITING_FOR_RESPONSE) = range(2)
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
                self._get_local_cache_callback,
                self._write_callback)

    def async_list_bookmarks(self):
        if self._bookmarks is None:
            self._cloudfilesynchronizerthread.async_read_local_cache()
        self._cloudfilesynchronizerthread.async_read()

    def add_bookmark(self, url, title, parent_dir_entry_guid):
        # Validate connection to cloud storage
        if self._bookmarks is None:
            raise NotConnectedToCloudStorage()

        parent = self._bookmarks

        # Look for parent dir in tree
        if parent_dir_entry_guid != -1 and self._bookmarks:
            dfs_stack = [self._bookmarks[0]]
            while dfs_stack:
                item = dfs_stack.pop()
                if item['guid'] == parent_dir_entry_guid:
                    parent = item['childen']
                for child in item['children']:
                    dfs_stack.append(child)
            else:
                print("Did not find parent dir")

        if parent is not None:
            parent.append({'url': url, 'name': title, 'guid': uuid.uuid4().hex})
            # Write the local file (TODO do this asynchronously)
            self._async_write()

    def _list_bookmarks_callback(self, bookmarks_yaml):
        print("Bookmarks received from drive")
        #import pdb; pdb.set_trace()
        bookmarks_yaml = bookmarks_yaml.decode('utf-8')
        self._update_local_copy(bookmarks_yaml)

        print("Bookmarks received from cloud. Validating file structure...")
        was_fix_needed = self._fix_bookmarks()

        if was_fix_needed:
            print("Writing fixed bookmarks...")
            self._async_write()
        else:
            print("No fix needed.")
            self._list_bookmarks_main_glib_loop_callback(self._bookmarks, is_connected=True)

    def _fix_bookmarks(self):
        was_fix_needed = False
        
        # Scan the bookmarks tree to fix missing attributes
        if self._bookmarks:

            # Scan items with DFS
            dfs_stack = [self._bookmarks[0]]
            while dfs_stack:
                item = dfs_stack.pop()
                if not isinstance(item, dict):
                    raise ValueError("Found a non-dict construct in yaml file")
                if 'guid' not in item:
                    print("Adding guid")
                    item['guid'] = uuid.uuid4().hex
                    was_fix_needed = True
                if 'children' not in item:
                    item['children'] = []
                    print("Adding children")
                    was_fix_needed = True
                for child in item['children']:
                    dfs_stack.append(child)

        return was_fix_needed

    def _get_local_cache_callback(self, bookmarks_yaml_cache):
        print("Bookmarks read from local cache.")
        if self._bookmarks is None:
            self._update_local_copy(bookmarks_yaml_cache)
            self._list_bookmarks_main_glib_loop_callback(self._bookmarks, is_connected=False)
        else:
            print("Bookmarks read from local cache, but local cache is not empty.")

    def _update_local_copy(self, encoded_yaml):
        try:
            self._bookmarks = yaml.load(encoded_yaml)
        except:
            print("Could not read local cache YAML file: {}".format(traceback.format_exc()))
        if self._bookmarks is None:
            self._bookmarks = []

    def _async_write(self):
        contents = yaml.dump(self._bookmarks, encoding='utf-8', allow_unicode=True)
        # Write the file to cloud
        self._cloudfilesynchronizerthread.async_write(contents)

    def _write_callback(self):
        print("Bookmarks written to cloud")
        # Wrote to cloud once. Invoking callback to update bookmarks
        self._list_bookmarks_main_glib_loop_callback(self._bookmarks, is_connected=True)
