from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class LightSleepTests(unittest.TestCase):
    def make_manager(self, elapsed=40, enabled=True):
        clock = types.SimpleNamespace(
            ticks_ms=Mock(side_effect=[100, 100 + elapsed]),
            ticks_diff=lambda a, b: a - b, sleep_ms=Mock())
        machine = types.SimpleNamespace(freq=Mock(return_value=240000000),
                                        lightsleep=Mock())
        ns = {}
        with patch.dict(sys.modules, {'machine': machine, 'time': clock}):
            exec(compile((ROOT / 'libs/power_manager.py').read_text(), 'power', 'exec'), ns)
        return ns['CpuPowerManager'](light_sleep_enabled=enabled), machine, clock

    def test_screen_off_sleeps_and_screen_on_uses_normal_delay(self):
        manager, machine, clock = self.make_manager()
        manager.pause(40, display_off=True)
        machine.lightsleep.assert_called_once_with(40)
        clock.sleep_ms.assert_not_called()
        manager.pause(40, display_off=False)
        clock.sleep_ms.assert_called_once_with(40)
        self.assertEqual(machine.lightsleep.call_count, 1)

    def test_early_wake_does_not_speed_up_motion_filter(self):
        manager, machine, clock = self.make_manager(elapsed=7)
        manager.pause(40, display_off=True)
        clock.sleep_ms.assert_called_once_with(33)

    def test_error_falls_back_and_is_not_retried(self):
        manager, machine, clock = self.make_manager(elapsed=5)
        machine.lightsleep.side_effect = OSError('unsupported')
        manager.pause(40, display_off=True)
        clock.sleep_ms.assert_called_with(35)
        manager.pause(40, display_off=True)
        clock.sleep_ms.assert_called_with(40)
        self.assertEqual(machine.lightsleep.call_count, 1)

    def test_missing_api_falls_back(self):
        manager, machine, clock = self.make_manager(elapsed=0)
        del machine.lightsleep
        manager.pause(40, display_off=True)
        self.assertFalse(manager.light_sleep_enabled)
        clock.sleep_ms.assert_called_once_with(40)

    def test_config_switch_disables_light_sleep(self):
        manager, machine, clock = self.make_manager(enabled=False)
        manager.pause(40, display_off=True)
        machine.lightsleep.assert_not_called()
        clock.sleep_ms.assert_called_once_with(40)

    def test_tick_rollover(self):
        manager, machine, clock = self.make_manager()
        period = 1 << 30
        clock.ticks_ms.side_effect = [period - 20, 20]
        clock.ticks_diff = lambda a, b: (a - b + period // 2) % period - period // 2
        manager.pause(40, display_off=True)
        clock.sleep_ms.assert_not_called()
