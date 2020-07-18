import string
import unicodedata
from curses.ascii import isprint
from fuzzywuzzy import fuzz


def filter_printable(string):
    if isinstance(string, unicode):
        result = unicodedata.normalize('NFKD', string).encode('ascii', 'ignore')
    else:
        result = string
    return string


import unicodedata, re, sys

all_chars = (unichr(i) for i in xrange(sys.maxunicode))
categories = {'Cc'}
control_chars = ''.join(c for c in all_chars if unicodedata.category(c) in categories)
# or equivalently and much more efficiently
control_chars = ''.join(map(unichr, range(0x00,0x20) + range(0x7f,0xa0)))

control_char_re = re.compile('[%s]' % re.escape(control_chars))

def remove_control_chars(s):
    return control_char_re.sub('', s)


class ListFilter(object):
    def __init__(self):
        self._search_key = ""

    def update_search_key(self, search_key):
        self._search_key = self._normalize(search_key).decode('utf-8','ignore')

    def _normalize(self, title):
        title = filter_printable(title)
        for c in [" ", "\n", "\t"]:
            title = title.replace(c, "")
        title = title.lower()
        return title

    def get_candidate_score(self, candidate):
        if not self._search_key:
            return 100
        candidate = filter_printable(candidate)
        #candidate = self._normalize(candidate)
        candidate = remove_control_chars(candidate)
        print("AAAAA" + candidate + "AAAAA")
        if candidate in self._search_key or self._search_key in candidate:
            return 100
        score = fuzz.ratio(self._search_key, candidate)
        return score
