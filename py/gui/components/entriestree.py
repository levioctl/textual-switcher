import base64
import traceback
import gi
from gi.repository import Gtk, Gio
from gi.repository.GdkPixbuf import Pixbuf, InterpType
import expiringdict
from utils import glib_wrappers
from gui.components import listfilter, scoremanager


(COL_NR_RECORD_TYPE,
 COL_NR_ICON,
 COL_NR_TITLE,
 COL_NR_ENTRY_ID_INT,
 COL_NR_ENTRY_ID_INT2,
 COL_NR_ENTRY_INFO_STR,
 COL_NR_ENTRY_ID_STR,
 ) = range(7)


(RECORD_TYPE_WINDOW,
 RECORD_TYPE_BROWSER_TAB,
 RECORD_TYPE_BOOKMARK_ENTRY,
 RECORD_TYPE_BOOKMARKS_DIR,
 ) = range(4)


KNOWN_ICON_TYPES = (
                    "x-icon",
                    "png",
                    "gif",
                    "x-iconbase64",
                    "pngbase64",
                    "jpeg",
                    "svg+xml",
                    )
KNOWN_BASE64_ICON_TYPES = (
                           "x-iconbase64",
                           "pngbase64",
                           #"svg+xml",
                           )


class EntriesTree(object):
    ONE_DAY_IN_SECONDS = 60 * 60 * 24
    ICON_SIZE = 25

    def __init__(self,
                 row_activated_callback,
                 treeview_keypress,
                 row_selected_callback):
        self._s = None
        self._tabs = {}
        self._windows = {}
        self._bookmarks = []
        self._pid_to_row_iter = {}
        self._prev_map = None
        self._next_map = None
        self.expanded_mode = True
        self._icon_cache = expiringdict.ExpiringDict(max_len=100, max_age_seconds=self.ONE_DAY_IN_SECONDS)
        self.tree = self._create_tree()
        self.treefilter = self._create_tree_filter()
        self.treeview = Gtk.TreeView.new_with_model(self.treefilter)
        self._row_selected_external_callback = row_selected_callback
        self.treeview.set_headers_visible(False)
        self._currently_selected_row = None
        self.treeview.connect("row-activated", row_activated_callback)
        self.treeview.connect("key-press-event", treeview_keypress)
        self.treeview.connect("cursor-changed", self._row_selected_callback)

        column = Gtk.TreeViewColumn("")

        # Create subcolumns
        subcolumn_icon = Gtk.CellRendererPixbuf()
        subcolumn_text = Gtk.CellRendererText()

        # Pack subcolumns to column
        column.pack_start(subcolumn_icon, False)
        column.pack_start(subcolumn_text, True)

        # Bind subcolumns
        column.add_attribute(subcolumn_icon, "pixbuf", COL_NR_ICON)
        column.add_attribute(subcolumn_text, "text", COL_NR_TITLE)
    
        self.treeview.append_column(column)

        self.treeview.set_level_indentation(5)
        self.treeview.set_enable_tree_lines(True)
        self._listfilter = listfilter.ListFilter()
        self._score_manager = scoremanager.ScoreManager()
        self.select_first_row()

    def _row_selected_callback(self, *_):
        # Get selected row
        _, _iter = self.treeview.get_selection().get_selected()
        model = self.treeview.get_model()
        if model is None:
            self.select_first_row()
            return
        if _iter is None:
            self.select_first_row()
            return
        row = model[_iter]

        # Store currently selected row ID
        if row is not None:
            row_id = self._get_row_unique_id(row)
            self._currently_selected_row = row_id
            self._row_selected_external_callback()

    def update_search_key(self, search_key):
        self._s = search_key
        self._listfilter.update_search_key(search_key)
        self._refresh()

    def _create_tree_filter(self):
        tree_filter = self.tree.filter_new()
        tree_filter.set_visible_func(self._should_row_be_visible)
        return tree_filter

    def _create_tree(self):
        tree = Gtk.TreeStore(int, Pixbuf, str, int, int, str, str)
        tree.set_default_sort_func(self._compare_windows)
        return tree

    def _should_row_be_visible(self, model, _iter, _):
        if not self._s:
            return True

        row = model[_iter]

        row_id = self._get_row_unique_id(row)

        return self.should_row_be_visible(row_id)

    def _refresh(self):
        self._update_visibility_map()
        self.treefilter.refilter()
        self.enforce_expanded_mode()
        self.tree.set_default_sort_func(self._compare_windows)
        self.select_best_matching_visible_row()

    def _find_first_row_of_record_type(self, record_type):
        model = self.treeview.get_model()
        row_iter = model.get_iter_first()
        result = None
        while row_iter is not None:
            # Get row from iterator
            row = model[row_iter]

            # Remove row if its a window or a tab
            xid = row[COL_NR_ENTRY_ID_INT] 
            if row[COL_NR_RECORD_TYPE] == record_type:
                # The following conversion is needed because of the use of treemodefilter
                result = self.treefilter.convert_iter_to_child_iter(row_iter)
                break

            row_iter = model.iter_next(row_iter)

        return result

    def _remove_all_rows_of_record_type(self, record_type):
        # Remove existing window entries
        do_windows_still_exist_in_list = True
        while do_windows_still_exist_in_list:
            # Find next window/tab (iterate from beginning at each removal since iterator becomes invalid)

            window_row_iter = self._find_first_row_of_record_type(record_type)
            was_a_window_found_in_list = window_row_iter is not None
            if was_a_window_found_in_list:
                self.tree.remove(window_row_iter)
            else:
                # No more windows/tabs
                do_windows_still_exist_in_list = False

    def update_windows(self, windows):
        # Update cache
        self._windows = windows

        # Remove existing treeview rows of windows
        self._remove_all_rows_of_record_type(RECORD_TYPE_WINDOW)

        # Populate treeview with rows for updated windows
        self._add_windows_and_tabs_to_tree()

        # Refresh view
        self._refresh()

    def _add_windows_and_tabs_to_tree(self):
        # Add windows to treeview
        for window_xid in sorted(self._windows):
            window = self._windows[window_xid]
            window_row_label = window.get_label()
            row = [RECORD_TYPE_WINDOW, window.icon, window.get_label(), window.get_xid(), 0, "", ""]
            row_iter = self.tree.append(None, row)

            if window.is_browser():
                self._pid_to_row_iter[window.get_pid()] = row_iter

    def update_tabs(self, pid, tabs):
        # Validate
        # Make sure window is in local cache
        matching_windows = [window for window in self._windows.itervalues() if window.get_pid() == pid]
        if not matching_windows:
            print("Received tabs for a nonexistent window: {}".format(pid))
            return
        # The following is commented out, as there can be mulltiple browser windows with same PID
        #if len(matching_windows) > 1:
        #    raise RuntimeError("Local cache contains multuple entries with same PID {}".format(pid))
        window = matching_windows[0]

        if not window.is_browser():
            print("Received tabs for a non-browser window: {}".format(pid))
            return

        # Update local cache of tabs
        self._tabs[pid] = tabs

        # Add tabs
        self._add_tabs_of_window_to_treeview(window)

        # Refresh view
        self._refresh()

    def update_bookmarks(self, bookmarks):
        # Update cache
        self._bookmarks = bookmarks

        # Remove the bookmark row
        self._remove_all_rows_of_record_type(RECORD_TYPE_BOOKMARKS_DIR)

        # Add rows with updated bookmarks
        self._add_bookmarks_entries_to_tree()

        # Refresh view
        self._refresh()

    def _add_bookmarks_entries_to_tree(self):
        # Add the bookmarks rows by scanning bookmarks tree with DFS
        root = {'guid': "ROOT", 'children': self._bookmarks}
        dfs_stack = [(root, None)]
        parent_dir = None
        item = None
        row_iter = None
        while dfs_stack:
            bookmark, parent_row_iter = dfs_stack.pop()

            icon = gi.repository.GdkPixbuf.Pixbuf.new_from_file("/usr/share/textual-switcher/page_document_16748.ico")
            if bookmark['guid'] == 'ROOT':
                icon = gi.repository.GdkPixbuf.Pixbuf.new_from_file("/usr/share/textual-switcher/4096584-favorite-star_113762.ico")
                row = [RECORD_TYPE_BOOKMARKS_DIR, icon, "Bookmarks", 0, 0, "", bookmark['guid']]
            elif "url" in bookmark:
                label = u"{} ({})".format(bookmark["name"], bookmark["url"])
                row = [RECORD_TYPE_BOOKMARK_ENTRY, icon, label, 0, 0, bookmark['url'], bookmark['guid']] 
            else:
                label = bookmark["name"]
                row = [RECORD_TYPE_BOOKMARKS_DIR, icon, label, 0, 0, bookmark['name'], bookmark['guid']] 

            # Add bookmark row
            row_iter = self.tree.append(parent_row_iter, row)

            if 'children' in bookmark:
                for child in bookmark['children']:
                    dfs_stack.append((child, row_iter))

    def enforce_expanded_mode(self):
        if self.expanded_mode:
            self.treeview.expand_all()
        else:
            self.treeview.collapse_all()

    def select_first_row(self):
        if len(self.tree):
            self.treeview.set_cursor(0)

    def _add_tabs_of_window_to_treeview(self, window):
        # Find row iter
        pid = window.get_pid()

        if pid in self._tabs:
            for tab in self._tabs[pid]:
                # Check if icon can be fetched now instead of fetching the URL contents

                # Try fetching tab icon
                icon = None
                tab_has_icon = "favIconUrl" in tab
                if tab_has_icon:
                    # Look in local cache first
                    icon = self._get_tab_icon_from_local_cache(tab)

                    # If not in local cache, check if icon contents is inline inside favIconUrl
                    if icon is None:
                        icon = self.get_icon_from_favicon_url(tab)

                    # If icon is still not found, then favIconUrl is a URL (and not inline image contents).
                    # Fetch it asynchronously (will icon will be updated later)
                    if icon is None:
                        self._async_get_tab_icon_contents_from_url(tab)
                else:
                    # Tab does not have an icon
                    #print("Tab {} does not have a favIconUrl".format(tab['title']))
                    pass

                # If no icon was found now, use the window icon in the meantime
                if icon is None:
                    icon = window.icon

                # Add row
                tab_row_iter = self.tree.append(self._pid_to_row_iter[pid],
                                [RECORD_TYPE_BROWSER_TAB,
                                icon,
                                tab['title'],
                                window.get_xid(),
                                tab['id'],
                                "",
                                ""
                                ]
                                )

                tab['row_iter'] = tab_row_iter

        else:
            pass

    def _update_tab_icon(self, tab):
        # Get row iter for tab
        if 'row_iter' in tab:
            tab_row_iter = tab['row_iter']
        else:
            print("Tab does not contain a tab_iter key")
            print(tab)
            return

        # Update row
        model = self.treeview.get_model()
        row = model[tab_row_iter]
        self.tree.set_value(tab_row_iter, COL_NR_ICON, self._icon_cache[tab['favIconUrl']])

    def select_best_matching_visible_row(self):
        max_score_uids = self._score_manager.get_max_score_uids()
        if max_score_uids is None:
            print("Max score UIDs is none, selecting first row")
            self.select_first_row()
            return

        self._next_map = {}
        self._prev_map = {}
        prev_path = None

        # Populate DFS stack with tree roots
        dfs_stack = []
        model = self.treeview.get_model()
        row_iter = model.get_iter_first()
        while row_iter is not None:
            row = model[row_iter]
            dfs_stack.append(row)
            row_iter = model.iter_next(row_iter)
            path = row.path.to_string()
        dfs_stack.reverse()

        if dfs_stack:
            max_score_row = None
            while dfs_stack:
                # Check if current row is max score row by UID
                row = dfs_stack.pop()
                uid = self._get_row_unique_id(row)
                if uid in max_score_uids:
                    max_score_row = row

                path = row.path.to_string()
                if prev_path is not None:
                    self._next_map[prev_path] = path
                    self._prev_map[path] = prev_path
                prev_path = path

                # Add children to stack
                children = []
                child_iter = model.iter_children(row.iter)
                while child_iter is not None:
                    row = model[child_iter]
                    children.append(row)
                    child_iter = model.iter_next(child_iter)
                dfs_stack.extend(reversed(children))

            if max_score_row is not None and self._s:
                self.treeview.set_cursor(max_score_row.path)
            else:
                self.select_first_row()

    def get_value_of_selected_row(self, col_nr):
        _filter, _iter = self.get_selected_row()
        if _iter is None:
            try:
                _iter = _filter.get_iter(0)
            except ValueError:
                # Nothing to select
                return None
        return _filter.get_value(_iter, col_nr)

    def get_selected_row(self):
        selection = self.treeview.get_selection()
        return selection.get_selected()

    def _get_row_unique_id(self, row):
        return row[COL_NR_ENTRY_ID_INT], row[COL_NR_ENTRY_ID_INT2], row[COL_NR_ENTRY_ID_STR]

    def _compare_windows(self, model, iter_a, iter_b, user_data):
        record_a_type = model[iter_a][COL_NR_RECORD_TYPE]
        record_b_type = model[iter_b][COL_NR_RECORD_TYPE]

        if record_a_type not in(RECORD_TYPE_BROWSER_TAB, RECORD_TYPE_WINDOW):
            return -1
        if record_b_type not in(RECORD_TYPE_BROWSER_TAB, RECORD_TYPE_WINDOW):
            return 1

        window_a_id = model[iter_a][COL_NR_ENTRY_ID_INT]
        window_b_id = model[iter_b][COL_NR_ENTRY_ID_INT]

        window_a = self._windows[window_a_id]
        window_b = self._windows[window_b_id]

        window_a_score = self.get_score(window_a.window.title, window_a.window.wm_class)
        window_b_score = self.get_score(window_b.window.title, window_b.window.wm_class)

        if window_a_score > window_b_score:
            print(window_a.window.title, '>', window_b.window.title)
            return -1
        elif window_b_score > window_a_score:
            print(window_b.window.title, '>', window_a.window.title)
            return 1
        return 0

    def _async_get_tab_icon_contents_from_url(self, tab):
        # Async read icon from URL by scheduling the ready callback
        fav_icon_url = tab["favIconUrl"]

        # Parse image as URL
        def callback(url, image):
            icon = self._store_image_contents_in_icon_cache(tab, image)

            # Invoke update callback
            if icon is not None:
                self._update_tab_icon(tab)

        glib_wrappers.async_get_url(fav_icon_url, callback)

    def get_icon_from_favicon_url(self, tab):
        image = self.try_parse_icon_from_favicon_inline_contents(tab['favIconUrl'])

        # Convert to pixbuf
        if image is not None:
            image = self._store_image_contents_in_icon_cache(tab, image)

        return image

    def _store_image_contents_in_icon_cache(self, tab, image):
        image = self._get_pixbuf_from_image_contents(image)

        # Update cache
        url = tab['favIconUrl']
        if image is None:
            print(traceback.format_exc())
            print("Error generating icon from URL (first 20 chars): {}. tab title: {}".format(url[:20], tab['title']))
        else:
            self._icon_cache[url] = image

        return image

    def _get_tab_icon_from_local_cache(self, tab):
        result = None

        # Fetch icon from local cache, if exists
        if 'favIconUrl' in tab and tab['favIconUrl'] is not None:
            icon_url = tab['favIconUrl'] 
            is_tab_icon_in_cache = icon_url in self._icon_cache
            if is_tab_icon_in_cache:
                result = self._icon_cache[icon_url]
        
        return result

    def _get_pixbuf_from_image_contents(self, contents):
        result = None

        try:
            input_stream = Gio.MemoryInputStream.new_from_data(contents, None)
            pixbuf = Pixbuf.new_from_stream(input_stream, None)
            result = pixbuf.scale_simple(self.ICON_SIZE, self.ICON_SIZE, InterpType.BILINEAR)
        except:
            print(traceback.format_exc())
            print("Error generating icon from URL ")

        return result

    def _update_visibility_map_for_window_and_its_tabs(self, window_id, window):
        """Update visibility map with score of window and its tabs."""

        # Set title as token
        window_token = window.get_label()
        window_type_str = window.window.wm_class.decode('utf-8')
        window_score = self.get_score(window_token, window_type_str)
        window_uid = (window_id, 0, "")
        self._score_manager.set_score(window_uid, window_score, window.get_label())
        is_window_visible = self._score_manager.is_visible(window_uid)

        # Calculate tabs scores
        window_has_tabs = window.get_pid() in self._tabs
        if window_has_tabs and window.is_browser():
            tabs = self._tabs[window.get_pid()]
            for tab in tabs:
                tab_token = tab['title']
                tab_uid = (window_id, tab['id'], "")
                tab_score = self.get_score(tab_token, "tab")
                self._score_manager.set_score(tab_uid, tab_score, tab_token)
                is_window_visible = is_window_visible or self._score_manager.is_visible(tab_uid)

        self._score_manager.override_visiblity(window_uid, is_window_visible)

    def _lookup_visibility_map(self, row_id):
        return self._score_manager.is_visible(row_id)

    def should_row_be_visible(self, row_id):
        is_visible_according_to_map = self._lookup_visibility_map(row_id)

        if is_visible_according_to_map is None:
            should_be_visible = True
        else:
            should_be_visible = is_visible_according_to_map

        return should_be_visible

    def _update_visibility_map(self):
        # Initialize iterator to first row
        self._score_manager.reset()

        # Update visibility of windows and tabs
        for window_id, window in self._windows.iteritems():
            self._update_visibility_map_for_window_and_its_tabs(window_id, window)

        # Invoke recursive map update function on all root nodes
        for bookmark in self._bookmarks:
            self._update_visibility_map_recursively(bookmark)
        #uid = (0, 0, 'ROOT')
        #self._score_manager.override_visiblity(uid, is_there_a_visible_bookmark)

    def _update_visibility_map_recursively(self, bookmark):
        """Update visibility map for bookmark and all its subtree, and return whether it's visible (bool)."""
        # Update all child nodes while finding out if there's a visible descentant
        is_there_a_visible_descendent = False
        if 'children' in bookmark:
            for child_bookmark in bookmark['children']:
                # Update visibiliy map on child's descendents while maintaining is_there_a_visible_descendent,
                # by checking if one of them is visible
                is_there_a_descendant_in_child_subtree = self._update_visibility_map_recursively(child_bookmark)
                is_there_a_visible_descendent = is_there_a_visible_descendent or is_there_a_descendant_in_child_subtree

        score = self.get_score(bookmark['name'] + ' ' + bookmark.get('url', ''), 'bookmark')
        uid = (0, 0, bookmark['guid'])
        self._score_manager.set_score(uid, score, bookmark['name'])

        # Make node visible if it has a visible descendant or if the label matches
        if is_there_a_visible_descendent:
            self._score_manager.override_visiblity(uid, True)

        return self._score_manager.is_visible(uid)

    def get_score(self, title, type_str):
        score = self._listfilter.get_candidate_score(title)
        if type_str is not None and type_str:
            type_str_score = self._listfilter.get_candidate_score(type_str)
            score = max(score, type_str_score)
        return score

    def try_parse_icon_from_favicon_inline_contents(self, fav_icon_url):
        image = None

        for image_prefix in KNOWN_ICON_TYPES:
            # Try parsing image as inline
            image = None
            is_base64 = False

            # Populate `image` and `is_base64`
            if fav_icon_url.startswith("data:image/{},".format(image_prefix)):
                image_type, image = fav_icon_url.split('/', 1)[1].split(',', 1)
                if image_type in KNOWN_BASE64_ICON_TYPES:
                    is_base64 = True
            elif fav_icon_url.startswith("data:image/{};".format(image_prefix)):
                _, parameter_and_image = fav_icon_url.split('/', 1)[1].split(';', 1)

                if parameter_and_image.startswith("base64,"):
                    image = parameter_and_image.split(',', 1)[1]
                    is_base64 = True

            # Act on `image` and `base64`
            if image is not None:
                if is_base64:
                    image = base64.b64decode(image)
                break

        return image
