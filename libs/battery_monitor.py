"""Infrequent battery checks with hysteresis; no hardware dependencies."""
import time


class BatteryMonitor:
    def __init__(self, read_percentage, threshold=15, interval_ms=60000):
        self.read_percentage = read_percentage
        self.threshold = threshold
        self.interval_ms = interval_ms
        self.last_check = None
        self.warned = False

    def poll(self, now):
        if self.last_check is not None and time.ticks_diff(now, self.last_check) < self.interval_ms:
            return None
        self.last_check = now
        level = self.read_percentage()
        if level is None:
            return None
        if level >= self.threshold + 5:
            self.warned = False
        if level <= self.threshold and not self.warned:
            self.warned = True
            return level
        return None
