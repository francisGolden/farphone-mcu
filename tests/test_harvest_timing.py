import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock


class HarvestTimingTests(unittest.TestCase):
    def test_phase_times_and_cleanup_on_success_or_failure(self):
        tree = ast.parse(Path('libs/network/network_client.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'sync_session_event')
        for fail in (False, True):
            now = [0]
            def operation(duration, result, raises=False):
                def run(*args, **kwargs):
                    now[0] += duration
                    if raises:
                        raise OSError('timeout')
                    return result
                return run
            ns = dict(time=types.SimpleNamespace(ticks_ms=lambda: now[0], ticks_diff=lambda a,b:a-b),
                connect_wifi=operation(1400, True), send_harvest_raw=operation(200, True, fail),
                fetch_user_raw=operation(300, {'username': 'test'}),
                disconnect_wifi=operation(50, None), print=Mock())
            exec(compile(ast.Module(body=[fn], type_ignores=[]), 'sync', 'exec'), ns)
            timings = {'get': 9999}
            result = ns['sync_session_event']('u','s','p',1,'SUCCESSFUL',60,timings=timings)
            self.assertEqual(timings['wifi'], 1400)
            self.assertEqual(timings['post'], 200)
            self.assertEqual(timings['off'], 50)
            if fail:
                self.assertNotIn('get', timings)
                self.assertFalse(result)
            else:
                self.assertEqual(timings['get'], 300)
                self.assertEqual(result, {'username': 'test'})

    def test_screen_displays_unattempted_phase_and_dismisses(self):
        tree = ast.parse(Path('libs/frontend/ui_renderer.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        lcd = Mock()
        m5 = types.SimpleNamespace(Lcd=lcd, update=Mock(),
            BtnA=types.SimpleNamespace(wasPressed=Mock(return_value=True)),
            BtnB=types.SimpleNamespace(wasPressed=Mock(return_value=False)))
        ns = dict(M5=m5, Lcd=lcd, time=types.SimpleNamespace(sleep_ms=Mock()))
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui', 'exec'), ns)
        ui = ns['UiRenderer']()
        ui.show_harvest_timing({'wifi': 9000, 'total': 15000}, False)
        lcd.print.assert_any_call('Wi-Fi: 9.00s')
        lcd.print.assert_any_call('GET: --')
        lcd.print.assert_any_call('Total: 15.00s')
        lcd.print.assert_any_call('Sync failed')
        self.assertTrue(ui.is_display_on)
