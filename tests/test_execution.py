from pathlib import Path
import sys
import tempfile
import unittest
from printkit.common import ForgeError
from printkit.execution import run_process

class ExecutionTests(unittest.TestCase):
    def test_timeout_and_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            result=run_process([sys.executable,'-c','import os; assert "GITHUB_TOKEN" not in os.environ; print("ok")'],root,root/'log.txt')
            self.assertEqual(result['exit_code'],0)
            self.assertFalse(result['controls']['network_isolation'])
            with self.assertRaises(ForgeError) as ctx:
                run_process([sys.executable,'-c','import time; time.sleep(2)'],root,root/'timeout.txt',timeout=.1)
            self.assertEqual(ctx.exception.finding,'execution_timeout')
    def test_environment_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ForgeError):
                run_process([sys.executable,'-c','pass'],directory,Path(directory)/'log',env_extra={'LD_PRELOAD':'evil'})

class ValidatorProcessTests(unittest.TestCase):
    def test_hard_timeout_and_crash(self):
        import time
        from unittest.mock import patch
        from printkit.isolated_validation import validate_bounded
        with patch('printkit.validation.validate_mesh',side_effect=lambda *_: time.sleep(2)):
            with self.assertRaises(ForgeError) as ctx:
                validate_bounded('unused',{},timeout=.05)
            self.assertEqual(ctx.exception.finding,'validator_timeout')
        with patch('printkit.validation.validate_mesh',side_effect=RuntimeError('broken')):
            with self.assertRaises(ForgeError) as ctx:
                validate_bounded('unused',{})
            self.assertEqual(ctx.exception.finding,'validator_crash')
