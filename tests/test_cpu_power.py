import ast
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class CpuPowerTests(unittest.TestCase):
    def make_manager(self, frequency):
        machine = types.SimpleNamespace(freq=Mock(return_value=frequency))
        ns = {}
        with patch.dict(sys.modules, {'machine': machine}):
            exec(compile((ROOT / 'libs/power_manager.py').read_text(), 'power', 'exec'), ns)
        return ns['CpuPowerManager'](), machine.freq

    def test_display_sleep_and_wake_restore_original_frequency(self):
        manager, freq = self.make_manager(160000000)
        tree = ast.parse((ROOT / 'libs/frontend/ui_renderer.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef)
                    and n.name in ('__init__', 'display_on', 'display_off')]
        lcd = Mock()
        ns = {'Lcd': lcd}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui', 'exec'), ns)
        ui = ns['UiRenderer'](power_manager=manager)
        ui.display_off()
        self.assertFalse(ui.is_display_on)
        freq.assert_called_with(80000000)
        ui.display_on()
        self.assertTrue(ui.is_display_on)
        freq.assert_called_with(160000000)
        ui.display_on()
        self.assertEqual(freq.call_count, 3)  # Read, lower, restore.

    def test_does_not_increase_an_already_lower_frequency(self):
        manager, freq = self.make_manager(40000000)
        manager.set_idle(True)
        freq.assert_called_with(40000000)

    def test_unsupported_frequency_does_not_abort_application(self):
        manager, freq = self.make_manager(240000000)
        freq.side_effect = ValueError('unsupported frequency')
        manager.set_idle(True)
        self.assertFalse(manager.is_idle)

    def test_failed_restore_can_be_retried(self):
        manager, freq = self.make_manager(240000000)
        manager.set_idle(True)
        freq.side_effect = OSError('busy')
        manager.set_idle(False)
        self.assertTrue(manager.is_idle)
        freq.side_effect = None
        manager.set_idle(False)
        self.assertFalse(manager.is_idle)
        freq.assert_called_with(240000000)
