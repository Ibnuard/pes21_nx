"""Committed features must not disappear from isolated runtime builds."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'stage', Path(__file__).resolve().parents[1]/'tools/prepare_visual_runtime_build.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class RuntimeStagingTests(unittest.TestCase):
    def test_delta_contains_committed_and_uncommitted_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def git(*args):
                return subprocess.run(['git', *args], cwd=root, check=True,
                                      capture_output=True, text=True).stdout.strip()
            git('init')
            git('config', 'user.name', 'Host test')
            git('config', 'user.email', 'test@localhost')
            path = root/'runtime.txt'
            path.write_text('baseline\n')
            git('add', '.')
            git('commit', '-m', 'baseline')
            baseline = git('rev-parse', 'HEAD')
            path.write_text('baseline\naccepted cursor and helper\n')
            git('add', '.')
            git('commit', '-m', 'accepted features')
            path.write_text('baseline\naccepted cursor and helper\nnew lab\n')
            revision, patch = stage.revision_delta(root, baseline, ('runtime.txt',))
            self.assertEqual(revision, baseline)
            self.assertIn(b'+accepted cursor and helper', patch)
            self.assertIn(b'+new lab', patch)
            self.assertNotIn('+accepted cursor and helper', git('diff'))


if __name__ == '__main__':
    unittest.main()
