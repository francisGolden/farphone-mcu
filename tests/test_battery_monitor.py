import unittest
from unittest.mock import Mock, patch
from libs import battery_monitor


class BatteryMonitorTests(unittest.TestCase):
    def test_one_warning_until_recharged_and_unknown_is_not_empty(self):
        read = Mock(side_effect=[None, 16, 15, 14, 16, 19, 20, 15])
        monitor = battery_monitor.BatteryMonitor(read)
        with patch.object(battery_monitor.time, 'ticks_diff', lambda a, b: a-b, create=True):
            results = [monitor.poll(t*60000) for t in range(8)]
        self.assertEqual(results, [None, None, 15, None, None, None, None, 15])

    def test_infrequent_checks_and_tick_wrap(self):
        read = Mock(return_value=0)
        monitor = battery_monitor.BatteryMonitor(read)
        period = 1 << 30
        diff = lambda a,b: ((a-b+period//2) % period)-period//2
        with patch.object(battery_monitor.time, 'ticks_diff', diff, create=True):
            self.assertEqual(monitor.poll(period-30000), 0)
            self.assertIsNone(monitor.poll(100))
            read.assert_called_once()
            self.assertIsNone(monitor.poll(30000))
            self.assertEqual(read.call_count, 2)
