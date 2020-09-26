import json
import subprocess
import uuid
import os.path
import yaml
import traceback
from utils.drive import cloudfilesynchronizerthread



CHROME_BOOKMARKS_PATH = os.path.expanduser(r"~/.config/google-chrome/Default/Bookmarks")
FIREFOX_CONFIG_PATH = os.path.expanduser(r"~/.mozilla/firefox/")


class NotConnectedToCloudStorage(Exception): pass


ALLOWED_ENTRY_KEYS = ['guid', 'name', 'children']


class BookmarksStore(object):
    (STATE_IDLE,
     STATE_WAITING_FOR_RESPONSE) = range(2)

    def __init__(self,
                 list_bookmarks_main_glib_loop_callback,
                 connected_to_cloud_callback,
                 disconnected_from_cloud_callback,
                 explicit_authentication_needed_external_callback):
        self._bookmarks = None
        self._list_bookmarks_main_glib_loop_callback = list_bookmarks_main_glib_loop_callback
        self._explicit_authentication_needed_external_callback = (
                explicit_authentication_needed_external_callback)
        self._cloudfilesynchronizerthread = cloudfilesynchronizerthread.CloudFileSynchronizerThread(
                "bookmarks.yaml",
                connected_to_cloud_callback,
                disconnected_from_cloud_callback,
                self._list_bookmarks_callback,
                self._get_local_cache_callback,
                self._explicit_authentication_needed_callback,
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

        # Find parent node
        parent = self.get_entry_by_guid(parent_dir_entry_guid)
        if 'children' not in parent:
            if 'url' in parent:
                raise ValueError("Cannot add child bookmark to non-folder bookmark", parent_dir_entry_guid)
            else:
                # Fix entry
                parent['children'] = []

        parent['children'].append({'url': url, 'name': title, 'guid': uuid.uuid4().hex})
        # Write the local file (TODO do this asynchronously)
        self._async_write()

    def remove(self, bookmark_id, recursive=False):
        # Validate connection to cloud storage
        if self._bookmarks is None:
            raise NotConnectedToCloudStorage()

        item = self.get_entry_by_guid(bookmark_id)
        parent = self.get_parent_of_entry(bookmark_id)
        is_parent = 'children' in item and item['children']
        if is_parent and not recursive:
            raise ValueError("Cannot remove an entry with children")
        else:
            parent['children'].remove(item)

        self._async_write()

    def add_folder(self, parent_folder_guid, folder_name):
        # Generate folder
        folder = {'name': folder_name, 'guid': uuid.uuid4().hex}

        # Find parent
        parent = self.get_entry_by_guid(parent_folder_guid)

        # Fix entry if no 'children' key
        if 'url' not in parent and 'children' not in 'parent':
            parent['children'] = []

        parent['children'].append(folder)

        self._async_write()

    def rename(self, guid, new_name):
        is_root = guid == 'ROOT'
        if is_root:
            raise ValueError(guid, "Cannot rename the root node")

        entry = self.get_entry_by_guid(guid)

        entry['name'] = new_name

        self._async_write()

    def is_node_a_under_node_b(self, node_a, node_b):
        current_node = node_a
        while True:
            if current_node['guid'] == node_b['guid']:
                return True
            if current_node['guid'] == 'ROOT':
                break

            current_node = self.get_parent_of_entry(current_node['guid'])
        return node_a['guid'] == node_b['guid']

    def move_entry(self, guid, dest_parent_guid):
        # Validate not moving root
        is_trying_to_move_root = guid == 'ROOT'
        if is_trying_to_move_root:
            raise ValueError(guid, "Cannot move the root dir")

        entry = self.get_entry_by_guid(guid)
        
        # Find entries
        dest_parent = self.get_entry_by_guid(dest_parent_guid)
        # Fix entry if it has no 'children' key
        if 'children' not in dest_parent and 'url' not in dest_parent:
            dest_parent['children'] = []

        # Validate dest is not under src
        if self.is_node_a_under_node_b(dest_parent, entry):
            raise ValueError("Cannot move an entry to one if its children")

        # Remove from current parent
        parent = self.get_parent_of_entry(guid)
        parent['children'].remove(entry)

        # Add to parent
        dest_parent['children'].append(entry)

        # Write
        self._async_write()

    def move_children_of_entry(self, guid, dest_parent_guid):
        # Validate not moving root
        is_trying_to_move_root = guid == 'ROOT'
        if is_trying_to_move_root:
            raise ValueError(guid, "Cannot move all children of root dir")

        entry = self.get_entry_by_guid(guid)
        
        # Find entries
        dest_parent = self.get_entry_by_guid(dest_parent_guid)
        # Fix entry if it has no 'children' key
        if 'children' not in dest_parent and 'url' not in dest_parent:
            dest_parent['children'] = []

        # Validate dest is not under src
        if self.is_node_a_under_node_b(dest_parent, entry):
            raise ValueError("Cannot move an entry to one if its children")

        # Remove children entry
        children = entry['children']
        entry['children'] = []

        # Add to parent
        dest_parent['children'].extend(children)

        # Write
        self._async_write()

    def import_from_firefox(self):
        bookmarks_filename = self._find_latest_bookmarks_filename()
        if bookmarks_filename is None:
            raise RuntimeError("Did not find firefox bookmarks file")
        cmd = ["/usr/share/textual-switcher/dejsonlz4", bookmarks_filename]
        bookmarks_json = subprocess.check_output(cmd)
        firefox_bookmarks = json.loads(bookmarks_json)
        firefox_bookmarks = firefox_bookmarks.get('children', [])

        def convert_chrome_entry_to_local_entry(firefox_entry):
            local_entry = dict(firefox_entry)
            guid = firefox_entry['guid']
            name = firefox_entry['title']
            for key in local_entry.keys():
                if key not in ALLOWED_ENTRY_KEYS:
                    del local_entry[key]

            local_entry['children'] = []
            local_entry['guid'] = guid
            local_entry['name'] = name

            return local_entry

        self._import_bookmarks(firefox_bookmarks, convert_chrome_entry_to_local_entry)

    def import_from_chrome(self):
        with open(CHROME_BOOKMARKS_PATH) as chrome_bookmarks:
            chrome_bookmarks = json.load(chrome_bookmarks)['roots']
        chrome_bookmarks = [chrome_bookmarks[root_name] for root_name in ['synced', 'bookmark_bar', 'other']
                            if root_name in chrome_bookmarks if 'children' in bookmarks[root_name]]

        def convert_chrome_entry_to_local_entry(chrome_entry):
            local_entry = dict(chrome_entry)
            guid = chrome_entry['guid']
            for key in local_entry.keys():
                if key not in ALLOWED_ENTRY_KEYS:
                    del local_entry[key]

            local_entry['children'] = []
            local_entry['guid'] = guid

            return local_entry

        self._import_bookmarks(chrome_bookmarks, convert_callback)

    def _import_bookmarks(self, bookmarks, convert_bookmark_to_local_bookmark):
        # Populate DFS stack with roots of chrome bookmarks tree
        dfs_stack = [(root, None) for root in bookmarks]

        while dfs_stack:
            chrome_entry, parent_local_entry = dfs_stack.pop()

            # Find parent to contain bookmark
            if parent_local_entry is None:
                children_of_parent = self._bookmarks
            else:
                children_of_parent = parent_local_entry['children']

            # Convert chrome entry to local entry
            children = None
            if 'children' in chrome_entry:
                children = chrome_entry['children']
            local_entry = convert_bookmark_to_local_bookmark(chrome_entry)

            # Add entry if it does not exist already
            already_exists = local_entry['guid'] in [entry['guid'] for entry in children_of_parent]
            if already_exists:
                print("bookmark already exists")
            else:
                children_of_parent.append(local_entry)

            # Popluate DFS stack wich node's children
            if children is not None:
                # Add child and parent
                children = [(child, local_entry) for child in children]
                dfs_stack.extend(children)

        self._async_write()

    def get_parent_of_entry(self, guid):
        """Get parent entry of the entry with the given GUID.

        If parent is root, return 'ROOT'.
        If GUID does not exist, return None.
        """
        _, parent = self._get_entry_and_parent_by_entry_guid(guid)
        return parent

    def get_entry_by_guid(self, guid):
        item, _ = self._get_entry_and_parent_by_entry_guid(guid)
        return item

    def connect_to_drive_explicitly(self):
        self._cloudfilesynchronizerthread.try_to_connect_explicitly()

    def is_connected_to_drive(self):
        self._cloudfilesynchronizerthread.is_connected_to_drive()

    def _find_latest_bookmarks_filename(self):
        latest_updated_bookmarks_file = None

        # Find all bookmarks filenames
        bookmarks_files = []
        for root, dirs, files in os.walk(FIREFOX_CONFIG_PATH):
            bookmarks_files.extend([os.path.join(root, basename) for basename in files if
                                    basename.startswith("bookmarks-") and basename.endswith(".jsonlz4")])

        # Find latest modified bookmark file
        if bookmarks_files:
            latest_updated_bookmarks_file = max(bookmarks_files, key=os.path.getmtime)

        return latest_updated_bookmarks_file

    def _get_entry_and_parent_by_entry_guid(self, guid):
        if self._bookmarks is None:
            raise RuntimeError("Bookmarks were not read yet")

        # Find parent dir of bookmark
        dfs_stack = [(self._bookmarks[0], None)]
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

        if item is None:
            raise ValueError("Did not find a bookmark with GUID: {}".format(bookmark_id))
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
            self._invoke_external_bookmark_update_callback(is_connected=True)

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
            self._invoke_external_bookmark_update_callback(is_connected=False)
        else:
            print("Bookmarks read from local cache, but local cache is not empty.")

    def _explicit_authentication_needed_callback(self):
        print('Please authenticate using web browser')
        self._explicit_authentication_needed_external_callback()

    def _update_local_copy(self, encoded_yaml):
        self._bookmarks = [{'guid': 'ROOT', 'children': []}]
        try:
            self._bookmarks[0]['children'].extend(yaml.load(encoded_yaml)['children'])
        except:
            print("Could not read local cache YAML file: {}".format(traceback.format_exc()))

    def _async_write(self):
        assert self._bookmarks is not None
        assert len(self._bookmarks) == 1
        contents = yaml.dump(self._bookmarks[0], encoding='utf-8', allow_unicode=True)
        # Write the file to cloud
        self._cloudfilesynchronizerthread.async_write(contents)

    def _write_callback(self):
        print("Bookmarks written to cloud")
        # Wrote to cloud once. Invoking callback to update bookmarks
        self._invoke_external_bookmark_update_callback(is_connected=True)

    def _invoke_external_bookmark_update_callback(self, is_connected):
        bookmarks = self._bookmarks
        self._list_bookmarks_main_glib_loop_callback(bookmarks[0]['children'], is_connected=is_connected)
