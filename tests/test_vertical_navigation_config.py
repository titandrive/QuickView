import os
import tempfile
import unittest
from unittest.mock import patch
import config

class VerticalNavigation(unittest.TestCase):
    def test_values_and_environment_override(self):
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.conf') as f:
            with patch.dict(os.environ, {}, clear=True):
                for raw, expected in [('true', True), ('false', False), ('yes', True),
                                      ('off', False), ('1', True), ('0', False),
                                      ('invalid', True)]:
                    with self.subTest(value=raw):
                        f.seek(0)
                        f.truncate()
                        f.write('[navigation]\nvertical_navigation = ' + raw + '\n')
                        f.flush()
                        self.assertIs(config.load(f.name)['vertical_navigation'], expected)
                os.environ['QUICKVIEW_VERTICAL_NAVIGATION'] = 'false'
                self.assertIs(config.load(f.name)['vertical_navigation'], False)

if __name__ == '__main__':
    unittest.main()
