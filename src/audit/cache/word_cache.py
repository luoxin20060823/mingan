from __future__ import annotations

import threading

from ..repository.word_repo import WordRepository


class WordLibraryCache:
    def __init__(self, repo: WordRepository):
        self._repo = repo
        self._lock = threading.RLock()
        self._automaton = None

    def get_automaton(self):
        with self._lock:
            if self._automaton is None:
                self._automaton = self._repo.list_words()
            return self._automaton

    def invalidate(self) -> None:
        with self._lock:
            self._automaton = None
