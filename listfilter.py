from fuzzywuzzy import fuzz


class ListFilter(object):
    def __init__(self):
        self._search_key = ""

    def update_search_key(self, search_key):
        self._search_key = self._normalize(search_key)

    def _normalize(self, title):
        for c in [" ", "\n", "\t"]:
            title = title.replace(c, "")
        title = title.lower()
        return title

    def get_candidate_score(self, candidate):
        if not self._search_key:
            return 100
        candidate = self._normalize(candidate)
        search_key = unicode(self._search_key, 'utf-8')
        if candidate in search_key or search_key in candidate:
            return 100
        return fuzz.ratio(search_key, candidate)
