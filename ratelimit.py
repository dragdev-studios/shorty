from datetime import datetime, timedelta


class Bucket:

    def __init__(self, hits: int, per: float):
        self.hits = hits
        self.per = per
        self.used = 0
        self._expire = datetime.min
        self._expire_calc()

    def _expire_calc(self):
        self.used = 0
        self._expire = datetime.utcnow() + timedelta(seconds=self.per)

    @property
    def ratelimited(self):
        if self.hits < self.used and datetime.utcnow() < self._expire:
            return True
        self._expire_calc()
        return False
        
    def __add__(self, other: int):
        self.used += other
        return self
