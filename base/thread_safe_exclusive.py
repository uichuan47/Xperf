
"""
线程安全的独占对象，基于threading.Lock
"""

import threading


class ThreadSafeExclusive(object):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.occupier = None

    def occupy(self, occupier) -> bool:
        if self.lock.locked():
            return False
        self.occupier = occupier
        self.lock.acquire()
        return True

    def release(self) -> None:
        self.occupier = None
        if self.lock.locked():
            self.lock.release()

    def occupied(self) -> bool:
        return self.lock.locked()
