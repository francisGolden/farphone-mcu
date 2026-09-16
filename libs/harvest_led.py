"""StickS3 green status LED: M5PM1 PWR_CFG bit 4, not ESP32 GPIO10.

Register reference: https://github.com/m5stack/M5PM1/blob/main/src/M5PM1.h
"""
import time
from libs.diagnostic_log import log


class HarvestLed:
    def __init__(self, bus=None):
        self.bus = None
        self.started = None
        self.is_on = None
        try:
            if bus is None:
                from hardware import I2C, Pin
                # UIFlow internal bus, shared with the IMU and power controller.
                bus = I2C(1, scl=Pin(48), sda=Pin(47), freq=100000)
            self.bus = bus
            self._set(False)
        except (ImportError, AttributeError, OSError, ValueError) as exc:
            self.bus = None
            log('[LED] Status LED unavailable:', type(exc).__name__)

    def _set(self, enabled):
        if self.bus is None or enabled == self.is_on:
            return
        try:
            # Read on each transition: preserve current power rail/charging bits.
            value = self.bus.readfrom_mem(0x6E, 0x06, 1)[0]
            value = (value | 0x10) if enabled else (value & ~0x10)
            self.bus.writeto_mem(0x6E, 0x06, bytes([value]))
            self.is_on = enabled
        except (OSError, ValueError) as exc:
            # No repeated bus errors in the focus loop; retry on next app launch.
            self.bus = None
            log('[LED] Status LED disabled:', type(exc).__name__)

    def update(self, ready, now):
        if not ready:
            self.started = None
            self._set(False)
            return
        if self.started is None or time.ticks_diff(now, self.started) >= 3000:
            self.started = now
        self._set(time.ticks_diff(now, self.started) < 200)
