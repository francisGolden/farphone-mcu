"""Host-side regression tests; no M5 hardware or MicroPython installation needed."""
import ast
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class PowerManagementTests(unittest.TestCase):
    def test_sync_always_deactivates_wifi(self):
        for function in ('initial_sync', 'sync_session_event'):
            for outcome in ('success', 'timeout', 'connect_error', 'request_error'):
                with self.subTest(function=function, outcome=outcome):
                    wlan = Mock()
                    modules = {
                        'network': types.SimpleNamespace(WLAN=lambda _: wlan, STA_IF=0),
                        'config': types.SimpleNamespace(),
                        'libs.offline_storage': types.SimpleNamespace(
                            get_pending_syncs=lambda: [], clear_pending_syncs=lambda: None),
                    }
                    ns = {}
                    with patch.dict(sys.modules, modules):
                        exec(compile((ROOT / 'libs/network/network_client.py').read_text(),
                                     'network_client.py', 'exec'), ns)
                    ns['connect_wifi'] = Mock(return_value=outcome != 'timeout')
                    if outcome == 'connect_error':
                        ns['connect_wifi'].side_effect = OSError('connect failed')
                    ns['fetch_user_raw'] = Mock(return_value={'username': 'test'})
                    ns['send_harvest_raw'] = Mock(return_value=True)
                    if outcome == 'request_error':
                        ns['fetch_user_raw'].side_effect = OSError('request failed')
                        ns['send_harvest_raw'].side_effect = OSError('request failed')
                    args = ['user'] if function == 'initial_sync' else [
                        'user', 'seed', 'plant', 1, 'SUCCESSFUL', 60]
                    ns[function](*args)
                    wlan.active.assert_called_once_with(False)

    def test_disconnect_failure_still_deactivates_wifi(self):
        tree = ast.parse((ROOT / 'libs/network/network_client.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                  and n.name == 'disconnect_wifi')
        wlan = Mock()
        wlan.disconnect.side_effect = OSError('disconnect failed')
        ns = {'wlan': wlan}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'disconnect', 'exec'), ns)
        ns['disconnect_wifi']()
        wlan.active.assert_called_once_with(False)

    def test_peek_uses_its_own_deadline(self):
        tree = ast.parse((ROOT / 'apps/farphone.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Compare)
                      and isinstance(n.test.left, ast.Attribute)
                      and n.test.left.attr == 'peek_count')
        code = compile(ast.Module(body=[branch], type_ignores=[]), 'peek', 'exec')
        # Wrap ticks as on MicroPython, including a deadline across rollover.
        period = 1 << 30
        ticks_diff = lambda a, b: (a - b + period // 2) % period - period // 2
        for start in (1000, period - 2000):
            for count, elapsed, expired in ((0, 5000, False), (0, 10001, True),
                                            (1, 4999, False), (1, 5000, True)):
                with self.subTest(start=start, count=count, elapsed=elapsed):
                    ns = dict(session=types.SimpleNamespace(peek_count=count,
                              peek_until_ms=(start + 5000) % period),
                              now=(start + elapsed) % period, last_activity_ms=start,
                              SCREEN_TIMEOUT_MS=10000,
                              time=types.SimpleNamespace(ticks_diff=ticks_diff))
                    exec(code, ns)
                    self.assertEqual(ns['display_expired'], expired)

    def test_stationary_tilt_eventually_allows_display_timeout(self):
        tree = ast.parse((ROOT / 'apps/farphone.py').read_text())
        branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If)
                      and isinstance(n.test, ast.Compare)
                      and isinstance(n.test.comparators[0], ast.Tuple)
                      and len(n.test.comparators[0].elts) == 3)
        code = compile(ast.Module(body=branch.body, type_ignores=[]), 'idle', 'exec')
        ui = types.SimpleNamespace(is_display_on=True)
        ui.display_off = lambda: setattr(ui, 'is_display_on', False)
        ui.display_on = lambda: setattr(ui, 'is_display_on', True)
        ns = dict(math=math, time=types.SimpleNamespace(ticks_diff=lambda a, b: a-b),
                  idle_gravity=[0., 0., 1.], acc_sample=(1., 0., 0.),
                  last_activity_ms=0, SCREEN_TIMEOUT_MS=10000, ui=ui,
                  render_current_ui=lambda: None)
        for now in range(0, 12000, 40):
            ns['now'] = now
            exec(code, ns)
        self.assertFalse(ui.is_display_on)
        ns.update(acc_sample=(0., 0., 1.), now=12000)
        exec(code, ns)
        self.assertTrue(ui.is_display_on)


if __name__ == '__main__':
    unittest.main()
