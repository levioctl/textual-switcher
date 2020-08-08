import gi
from gi.repository import Gtk
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gui import listfilter


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


ICON_SIZE = 25


class ScoreManager(object):
    ENTRY_VISIBILITY_LOWER_THRESHOLD_SCORE = 30

    def __init__(self):
        # All entities must exist in score map
        # If an entity also exists in visibilty map, its visibility is not set by score, but by the
        # visibility map
        self._score_map = {}
        self._visibilitiy_map = {}

    def set_score(self, uid, value):
        self._score_map[uid] = value

    def get_score(self, uid):
        return self._score_map.get(uid)

    def is_visible(self, uid):
        result = None
        if uid in self._visibilitiy_map:
            result = self._visibilitiy_map[uid]
        elif uid in self._score_map:
            result = self._score_map[uid] > self.ENTRY_VISIBILITY_LOWER_THRESHOLD_SCORE

        return result

    def override_visiblity(self, uid, value):
        assert isinstance(value, bool)
        self._visibilitiy_map[uid] = value

    def reset(self):
        self._score_map.clear()
        self._visibilitiy_map.clear()


class EntriesTree(object):
    def __init__(self,
                 row_activated_callback,
                 treeview_keypress,
                 get_tab_icon_callback,
                 row_selected_callback):
        self._windows = None
        self._bookmarks = None
        self._tabs = {}
        self._s = ""
        self._get_tab_icon_callback = get_tab_icon_callback
        self._score_manager = ScoreManager()
        self.tree = self._create_tree()
        self.listfilter = listfilter.ListFilter()
        self.treefilter = self._create_tree_filter()
        self.treeview = Gtk.TreeView.new_with_model(self.treefilter)
        self.treeview.set_headers_visible(False)
        self.treeview.connect("row-activated", row_activated_callback)
        self.treeview.connect("key-press-event", treeview_keypress)
        self.treeview.connect("cursor-changed", row_selected_callback)

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

    def _create_tree_filter(self):
        tree_filter = self.tree.filter_new()
        tree_filter.set_visible_func(self._filter_window_list_by_search_key)
        return tree_filter

    def _create_tree(self):
        tree = Gtk.TreeStore(int, Pixbuf, str, int, int, str, str)
        tree.set_sort_func(1, self._compare_windows)
        tree.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        return tree

    def _compare_windows(self, model, iter_a, iter_b, user_data):
        record_a_type = model[iter_a][COL_NR_RECORD_TYPE]
        record_b_type = model[iter_b][COL_NR_RECORD_TYPE]
        if record_a_type not in(RECORD_TYPE_BROWSER_TAB, RECORD_TYPE_WINDOW):
            return 1
        if record_b_type not in(RECORD_TYPE_BROWSER_TAB, RECORD_TYPE_WINDOW):
            return -1

        window_a_id = model[iter_a][COL_NR_ENTRY_ID_INT]
        window_b_id = model[iter_b][COL_NR_ENTRY_ID_INT]

        window_a = self._windows[window_a_id]
        window_b = self._windows[window_b_id]

        window_a_score = self._get_score(window_a.window.title, window_a.window.wm_class)
        window_b_score = self._get_score(window_b.window.title, window_b.window.wm_class)

        if window_a_score > window_b_score:
            return -1
        elif window_b_score > window_a_score:
            return 1
        return 0

    def _filter_window_list_by_search_key(self, model, _iter, _):
        if not self._s:
            return True

        row = model[_iter]
        is_visible_according_to_map = self._lookup_visibility_map(row)

        if is_visible_according_to_map is None:
            should_be_visible = True
        else:
            should_be_visible = is_visible_according_to_map

        return should_be_visible


    def _update_visibility_map_for_window_and_its_tabs(self, window_id, window):
        """Update visibility map with score of window and its tabs."""

        # Set title as token
        window_token = window.get_label()
        type_str = window.window.wm_class.decode('utf-8')
        window_score = self._get_score(window_token, type_str)
        window_uid = (window_id, 0, "")
        self._score_manager.set_score(window_uid, window_score)
        is_window_visible = self._score_manager.is_visible(window_uid)

        # Calculate tabs scores
        window_has_tabs = window.get_pid() in self._tabs
        if window_has_tabs and window.is_browser():
            tabs = self._tabs[window.get_pid()]
            for tab in tabs:
                tab_token = tab['title'] + u' ' + window_token
                tab_uid = (window_id, tab['id'], "")
                tab_score = self._get_score(tab_token, type_str)
                self._score_manager.set_score(tab_uid, tab_score)
                is_window_visible = is_window_visible or self._score_manager.is_visible(tab_uid)

        self._score_manager.override_visiblity(window_uid, is_window_visible)

    def refresh(self, windows, tabs, bookmarks, expanded_mode):
        self._windows = windows
        self._bookmarks = bookmarks
        self._tabs = tabs
        self.tree.clear()
        for window in self._windows.values():
            window_row_label = window.get_label()
            row = [RECORD_TYPE_WINDOW, window.icon, window.get_label(), window.get_xid(), 0, "", ""]
            row_iter = self.tree.append(None, row)

            if window.is_browser():
                self._add_tabs_of_window_to_tree(window, row_iter)


        # Add the bookmarks row
        root = {'guid': "ROOT", 'children': bookmarks}
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

            row_iter = self.tree.append(parent_row_iter, row)
            if 'children' in bookmark:
                for child in bookmark['children']:
                    dfs_stack.append((child, row_iter))


        self.enforce_expanded_mode(expanded_mode)
        self.select_first_window()

    def _get_score(self, title, type_str):
        score = self.listfilter.get_candidate_score(title)
        if type_str is not None and type_str:
            type_str_score = self.listfilter.get_candidate_score(type_str)
            score = max(score, type_str_score)
        return score

    def update_search_key(self, search_key):
        self._s = search_key
        self.listfilter.update_search_key(search_key)
        self._update_visibility_map(search_key)
        self.treefilter.refilter()

    #def _expand_row_by_iter(self, row_iter):
    #    model = self.treeview.get_model()
    #    row = model[row_iter]
    #    self.treeview.expand_row(row.path, True)

    def enforce_expanded_mode(self, expanded_mode):
        if expanded_mode:
            self.treeview.expand_all()
        else:
            self.treeview.collapse_all()

    def select_first_window(self):
        if len(self.tree):
            self.treeview.set_cursor(0)

    def _add_tabs_of_window_to_tree(self, window, row_iter):
        if window.get_pid() in self._tabs:
            for tab in self._tabs[window.get_pid()]:
                icon = self._get_tab_icon_callback(tab)
                if icon is None:
                    icon = window.icon
                else:
                    icon = icon.scale_simple(ICON_SIZE, ICON_SIZE, InterpType.BILINEAR)
                self.tree.append(row_iter,
                                 [RECORD_TYPE_BROWSER_TAB,
                                  icon,
                                  tab['title'],
                                  window.get_xid(),
                                  tab['id'],
                                  "",
                                  ""
                                  ]
                                 )

    def select_first_tab_under_selected_window(self):
        return
        # A bit of nasty GTK hackery
        # Find the selected row in the tree view model, using the window ID
        selected_window_id = self.get_value_of_selected_row(COL_NR_ENTRY_ID_INT)
        #row = self._get_selected_row()
        model = self.treeview.get_model()
        _iter = model.get_iter_first()
        row = None
        while _iter is not None:
            row = model[_iter]
            if row[COL_NR_ENTRY_ID_INT] == selected_window_id:
                break
            _iter = model.iter_next(_iter)

        title = self.get_value_of_selected_row(COL_NR_TITLE)
    
        # Select child row that best matches the search key (if matches more than the window row)
        if row != None:
            child_iter = model.iter_children(row.iter)
            best_row_so_far = None
            best_score_so_far = None
            while child_iter is not None:
                child_row = model[child_iter]
                child_title = child_row[COL_NR_TITLE]
                child_score = self.listfilter.get_candidate_score(child_title)
                if best_row_so_far is None or child_score > best_score_so_far:
                    best_row_so_far = child_row
                    best_score_so_far = child_score
                child_iter = model.iter_next(child_iter)

            # Select the child row if better score than window
            if best_row_so_far is not None:

                is_window = self.get_value_of_selected_row(COL_NR_RECORD_TYPE) == RECORD_TYPE_WINDOW
                if is_window:
                    window = self._windows[selected_window_id]
                    parent_score = self._get_score(window.window.title, window.window.wm_class)
                else:
                    title = self.get_value_of_selected_row(COL_NR_TITLE)
                    parent_score = self._get_score(title, "")

                if best_score_so_far >= parent_score:
                    # Selct tab
                    self.treeview.set_cursor(best_row_so_far.path)
                else:
                    # Select window
                    self.select_first_window()
            else:
                self.select_first_window()

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

    def _update_visibility_map(self, search_key):
        # Initialize iterator to first row
        self._score_manager.reset()

        # Update visibility of windows and tabs
        for window_id, window in self._windows.iteritems():
            self._update_visibility_map_for_window_and_its_tabs(window_id, window)

        # Invoke recursive map update function on all root nodes
        is_there_a_visible_bookmark = False
        for bookmark in self._bookmarks:
            is_there_a_visible_bookmark = is_there_a_visible_bookmark or self._update_visibility_map_recursively(bookmark)
        uid = (0, 0, 'ROOT')
        self._score_manager.override_visiblity(uid, is_there_a_visible_bookmark)

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

        score = self._get_score(bookmark['name'] + ' ' + bookmark.get('url', ''), 'bookmark')
        uid = (0, 0, bookmark['guid'])
        self._score_manager.set_score(uid, score)

        # Make node visible if it has a visible descendant or if the label matches
        if is_there_a_visible_descendent:
            self._score_manager.override_visiblity(uid, True)

        return self._score_manager.is_visible(uid)

    def _get_row_unique_id(self, row):
        return row[COL_NR_ENTRY_ID_INT], row[COL_NR_ENTRY_ID_INT2], row[COL_NR_ENTRY_ID_STR]

    def _set_entry_in_visibility_map(self, row, value):
        row_id = self._get_row_unique_id(row)
        self._score_manager.set_score(row_id, value)

    def _lookup_visibility_map(self, row):
        row_id = self._get_row_unique_id(row)
        return self._score_manager.is_visible(row_id)
