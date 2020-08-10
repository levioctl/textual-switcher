import operator


class ScoreManager(object):
    ENTRY_VISIBILITY_LOWER_THRESHOLD_SCORE = 30

    def __init__(self):
        # All entities must exist in score map
        # If an entity also exists in visibilty map, its visibility is not set by score, but by the
        # visibility map
        self._score_map = {}
        self._visibilitiy_map = {}

    def set_score(self, uid, value, debug=None):
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

    def get_max_score_uids(self):
        if not self._score_map:
            return None
        max_score = max(self._score_map.itervalues())
        return [uid for uid, score in self._score_map.iteritems() if score == max_score]

