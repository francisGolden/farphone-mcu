import unittest
from unittest.mock import Mock, patch
from libs import harvest_led


class HarvestLedTests(unittest.TestCase):
    def test_ready_only_pulse_preserves_power_bits(self):
        bus = Mock()
        register = [0xAF]
        def read(*args):
            return bytes(register)
        def write(address, reg, data):
            self.assertEqual((address, reg), (0x6E, 0x06))
            self.assertEqual(data[0] & ~0x10, register[0] & ~0x10)
            register[0] = data[0]
        bus.readfrom_mem.side_effect = read
        bus.writeto_mem.side_effect = write
        with patch.object(harvest_led.time, 'ticks_diff', lambda a,b:a-b, create=True):
            led = harvest_led.HarvestLed(bus)
            led.update(False, 0)
            self.assertEqual(bus.writeto_mem.call_count, 1)
            led.update(True, 100)
            self.assertTrue(register[0] & 0x10)
            led.update(True, 200)
            self.assertEqual(bus.writeto_mem.call_count, 2)
            led.update(True, 300)
            self.assertFalse(register[0] & 0x10)
            register[0] = 0xA7  # Another power API changes an unrelated bit.
            led.update(True, 3100)
            self.assertEqual(register[0], 0xB7)
            led.update(False, 3140)
            self.assertEqual(register[0], 0xA7)

    def test_wrap_and_unavailable_bus(self):
        bus = Mock(readfrom_mem=Mock(return_value=b'\x07'))
        period = 1 << 30
        diff = lambda a,b: ((a-b+period//2) % period)-period//2
        with patch.object(harvest_led.time, 'ticks_diff', diff, create=True):
            led = harvest_led.HarvestLed(bus)
            led.update(True, period-100)
            led.update(True, 120)
            self.assertFalse(led.is_on)
            led.update(True, 2900)
            self.assertTrue(led.is_on)
            bus.readfrom_mem.side_effect = OSError('I2C unavailable')
            led.update(False, 2940)
            self.assertIsNone(led.bus)
            calls = bus.readfrom_mem.call_count
            led.update(True, 6000)
            self.assertEqual(bus.readfrom_mem.call_count, calls)
