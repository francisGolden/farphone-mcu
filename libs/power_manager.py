"""Reduce CPU frequency while the application display is off."""
from libs.diagnostic_log import log as print
import machine
import time


class CpuPowerManager:
    def __init__(self, idle_hz=80000000, light_sleep_enabled=True):
        self.light_sleep_enabled = light_sleep_enabled
        self._sleep_reported = False
        self.idle_hz = idle_hz
        self.active_hz = None
        self.is_idle = False
        try:
            self.active_hz = machine.freq()
            print('[Power] Active CPU Hz:', self.active_hz)
        except (AttributeError, ValueError, OSError) as exc:
            print('[Power] CPU frequency control unavailable:', exc)

    def set_idle(self, idle):
        if self.active_hz is None or idle == self.is_idle:
            return
        target = min(self.idle_hz, self.active_hz) if idle else self.active_hz
        try:
            machine.freq(target)
            self.is_idle = idle
        except (AttributeError, ValueError, OSError) as exc:
            # Do not mark the transition successful; waking may retry restoration.
            print('[Power] CPU frequency change failed:', exc)

    def pause(self, duration_ms, display_off=False):
        """Timed light sleep only between app iterations, never during audio/sync.

        Keep the original polling delay even if a wake source returns early.
        Unsupported firmware falls back once, avoiding repeated error logging.
        """
        if duration_ms <= 0:
            return
        if not display_off or not self.light_sleep_enabled:
            time.sleep_ms(duration_ms)
            return
        started = time.ticks_ms()
        try:
            machine.lightsleep(duration_ms)
        except (AttributeError, ValueError, OSError, NotImplementedError) as exc:
            self.light_sleep_enabled = False
            print('[Power] Light sleep disabled; using normal delay:', exc)
        else:
            if not self._sleep_reported:
                print('[Power] Timed light sleep enabled')
                self._sleep_reported = True
        remaining = duration_ms - time.ticks_diff(time.ticks_ms(), started)
        if remaining > 0:
            time.sleep_ms(remaining)
