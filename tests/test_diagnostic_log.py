import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock


class DiagnosticLogTests(unittest.TestCase):
    def test_serial_output_is_opt_in(self):
        tree = ast.parse(Path('libs/diagnostic_log.py').read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        for enabled in (None, False, True):
            config = types.SimpleNamespace()
            if enabled is not None:
                config.SERIAL_LOG_ENABLED = enabled
            output = Mock()
            ns = {'config': config, 'print': output}
            exec(compile(ast.Module(body=[fn], type_ignores=[]), 'logger', 'exec'), ns)
            ns['log']('message', 42)
            if enabled:
                output.assert_called_once_with('message', 42)
            else:
                output.assert_not_called()

    def test_all_app_serial_prints_use_the_gated_logger(self):
        for directory in ('apps', 'libs'):
            for path in Path(directory).rglob('*.py'):
                if path.name == 'diagnostic_log.py':
                    continue
                tree = ast.parse(path.read_text())
                prints = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Name) and n.func.id == 'print']
                if prints:
                    self.assertTrue(any(isinstance(n, ast.ImportFrom)
                        and n.module == 'libs.diagnostic_log'
                        and any(a.name == 'log' and a.asname == 'print' for a in n.names)
                        for n in tree.body), str(path))
