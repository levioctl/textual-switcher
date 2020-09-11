import uuid
import os.path
import yaml
import traceback
from utils.drive import cloudfilesynchronizerthread


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
        self._cloudfilesynchronizerthread.start()

    def async_list_bookmarks(self):
        if self._bookmarks is None:
            self._cloudfilesynchronizerthread.async_read_local_cache()
        self._cloudfilesynchronizerthread.async_read()

    def add_bookmark(self, url, title, parent_dir_entry_guid):
        # Validate connection to cloud storage
        if self._bookmarks is None:
            raise NotConnectedToCloudStorage()

        if parent_dir_entry_guid == 'ROOT':
            parent = self._bookmarks
        else:
            parent = self.get_entry_by_guid(parent_dir_entry_guid)
            if 'children' not in parent:
                if 'url' in parent:
                    raise ValueError("Cannot add child bookmark to non-folder bookmark", parent_dir_entry_guid)
                else:
                    # Fix entry
                    parent['children'] = []
            parent = parent['children']

        if parent is not None:
            parent.append({'url': url, 'name': title, 'guid': uuid.uuid4().hex})
            # Write the local file (TODO do this asynchronously)
            self._async_write()

    def remove(self, bookmark_id):
        if not self._bookmarks:
            raise RuntimeError("Cannot remove bookmark, inner bookmarks collection is empty")

        item = self.get_entry_by_guid(bookmark_id)
        parent = self.get_parent_of_entry(bookmark_id)
        if parent == 'ROOT':
            self._bookmarks.remove(item)
        elif item is None:
            raise ValueError("Did not find a bookmark with GUID: {}".format(bookmark_id))
        else:
            is_parent = 'children' in item and item['children']
            if is_parent:
                raise ValueError("Cannot remove an entry with children")
            else:
                parent['children'].remove(item)

        self._async_write()

    def add_folder(self, parent_folder_guid, folder_name):
        is_parent_folder_root_folder = parent_folder_guid == 'ROOT'

        # Generate folder
        folder = {'name': folder_name, 'guid': uuid.uuid4().hex}

        if is_parent_folder_root_folder:
            self._bookmarks.append(folder)
        else:
            parent = self.get_entry_by_guid(parent_folder_guid)

            # Fix entry if no 'children' key
            if 'url' not in parent and 'children' not in 'parent':
                parent['children'] = []

            parent['children'].append(folder)

        self._async_write()

    def rename(self, guid, new_name):
        is_parent_folder_root_folder = guid == 'ROOT'

        if is_parent_folder_root_folder:
            raise ValueError(guid, "Cannot rename the root node")

        entry = self.get_entry_by_guid(guid)

        entry['name'] = new_name

        self._async_write()

    def get_parent_of_entry(self, guid):
        """Get parent entry of the entry with the given GUID.

        If parent is root, return 'ROOT'.
        If GUID does not exist, return None.
        """
        _, parent = self._get_entry_by_guid(guid)
        return parent

    def get_entry_by_guid(self, guid):
        item, _ = self._get_entry_by_guid(guid)
        return item

    def _get_entry_by_guid(self, guid):
        # Find parent dir of bookmark
        root = {'guid': "ROOT", 'children': self._bookmarks}
        dfs_stack = [(root, None)]
        parent_dir = None
        item = None
        while dfs_stack:
            item, parent_dir_candidate = dfs_stack.pop()
            if item['guid'] == guid:
                parent_dir = parent_dir_candidate
                break
            if 'children' in item:
                for child in item['children']:
                    dfs_stack.append((child, item))

        assert item in parent_dir["children"]

        return item, parent_dir

    def _list_bookmarks_callback(self, bookmarks_yaml):
        print("Bookmarks received from drive")
        bookmarks_yaml = bookmarks_yaml.decode('utf-8')
        self._update_local_copy(bookmarks_yaml)

        was_fix_needed = self._fix_bookmarks()

        if was_fix_needed:
            self._async_write()
        else:
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
