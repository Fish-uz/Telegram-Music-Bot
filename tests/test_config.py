import os
import unittest
from unittest.mock import patch

from core.config import Config, validate_required_credentials


class ConfigValidationTests(unittest.TestCase):
    def test_missing_credentials_raise_error(self):
        with patch.dict(os.environ, {"API_ID": "", "API_HASH": "", "BOT_TOKEN": ""}, clear=True):
            with self.assertRaises(ValueError):
                validate_required_credentials()

    def test_present_credentials_are_accepted(self):
        with patch.dict(os.environ, {"API_ID": "123456", "API_HASH": "abc", "BOT_TOKEN": "token"}, clear=True):
            values = validate_required_credentials()
            self.assertEqual(values["API_ID"], 123456)
            self.assertEqual(values["API_HASH"], "abc")
            self.assertEqual(values["BOT_TOKEN"], "token")


if __name__ == "__main__":
    unittest.main()
