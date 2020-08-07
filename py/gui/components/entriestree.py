import gi
from gi.repository import Gtk
from gi.repository.GdkPixbuf import Pixbuf, InterpType
from gui import listfilter


(COL_NR_RECORD_TYPE,
 COL_NR_ICON,
 COL_NR_TITLE,
 COL_NR_WINDOW_ID,
 COL_NR_ENTRY_INFO_INT,
 COL_NR_ENTRY_INFO_STR,
 COL_NR_ENTRY_INFO_STR2,
 ) = range(7)


(RECORD_TYPE_WINDOW,
 RECORD_TYPE_BROWSER_TAB,
 RECORD_TYPE_BOOKMARK_ENTRY,
 RECORD_TYPE_BOOKMARKS_DIR,
 ) = range(4)


ICON_SIZE = 25


class EntriesTree(object):
    def __init__(self,
                 row_activated_callback,
                 treeview_keypress,
                 get_tab_icon_callback,
                 row_selected_callback):
        self._windows = {}
        self._tabs = {}
        self._get_tab_icon_callback = get_tab_icon_callback
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

        window_a_id = model[iter_a][COL_NR_WINDOW_ID]
        window_b_id = model[iter_b][COL_NR_WINDOW_ID]

        window_a = self._windows[window_a_id]
        window_b = self._windows[window_b_id]

        window_a_score = self._get_score(window_a.window.title, window_a.window.wm_class)
        window_b_score = self._get_score(window_b.window.title, window_b.window.wm_class)

        if window_a_score > window_b_score:
            return -1
        elif window_b_score > window_a_score:
            return 1
        return 0

    def _filter_window_list_by_search_key(self, model, _iter, data):
        row = model[_iter]
        record_type = row[COL_NR_RECORD_TYPE]

        type_str = ""
        token = row[COL_NR_TITLE].decode('utf-8')
        # Find token and type_str according to record type
        if record_type in (RECORD_TYPE_WINDOW, RECORD_TYPE_BROWSER_TAB):
            window_id = row[COL_NR_WINDOW_ID]
            if window_id is 0 or window_id not in self._windows:
                return False

            token = row[COL_NR_TITLE].decode('utf-8')
            window = self._windows[window_id]
            if window.get_pid() in self._tabs:
                tab_id = row[COL_NR_ENTRY_INFO_STR]
                is_tab = tab_id >= 0
                if window.is_browser() and not is_tab:
                    tabs = self._tabs[window.get_pid()]
                    sep = unicode(' ', 'utf-8')
                    token += sep.join(tab['title'] for tab in tabs)
                elif is_tab:
                    matching = [tab for tab in self._tabs[window.get_pid()] if tab['id'] == tab_id]
                    if matching:
                        tab = matching[0]
                        token = tab['title']

                type_str = window.window.wm_class.decode('utf-8')

        if isinstance(token, str):
            token = unicode(token, 'utf-8')

        score = self._get_score(token, type_str)
        return score > 30

    def refresh(self, windows, tabs, bookmarks, expanded_mode):
        self._windows = windows
        self._tabs = tabs
        self.tree.clear()
        NON_TAB_FLAG = -1
        for window in self._windows.values():
            window_row_label = window.get_label()
            row = [RECORD_TYPE_WINDOW, window.icon, window.get_label(), window.get_xid(), NON_TAB_FLAG, "", ""]
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
                row = [RECORD_TYPE_BOOKMARKS_DIR, icon, "Bookmarks", 0, NON_TAB_FLAG, "", "ROOT"]
            elif "url" in bookmark:
                label = u"{} ({})".format(bookmark["name"], bookmark["url"])
                row = [RECORD_TYPE_BOOKMARK_ENTRY, icon, label, 0, -1, bookmark['url'], bookmark['guid']] 
            else:
                label = bookmark["name"]
                row = [RECORD_TYPE_BOOKMARKS_DIR, icon, label, 0, -1, bookmark['name'], bookmark['guid']] 

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
        self.listfilter.update_search_key(search_key)

    #def _expand_row_by_iter(self, row_iter):
    #    model = self.treeview.get_model()
    #    row = model[row_iter]
    #    self.treeview.expand_row(row.path, True)

    def enforce_expanded_mode(self, expanded_mode):
        if expanded_mode:
            print("Expanding all")
            self.treeview.expand_all()
        else:
            print("Collapsing all")
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
        # A bit of nasty GTK hackery
        # Find the selected row in the tree view model, using the window ID
        selected_window_id = self.get_value_of_selected_row(COL_NR_WINDOW_ID)
        #row = self._get_selected_row()
        model = self.treeview.get_model()
        _iter = model.get_iter_first()
        row = None
        while _iter is not None:
            row = model[_iter]
            if row[COL_NR_WINDOW_ID] == selected_window_id:
                break
            _iter = model.iter_next(_iter)

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
