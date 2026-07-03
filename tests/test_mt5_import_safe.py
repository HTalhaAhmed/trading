import unittest

from trading.brokers.mt5 import MT5Broker, MT5UnavailableError


class MT5ImportSafetyTests(unittest.TestCase):
    def test_mt5_optional_dependency(self):
        with self.assertRaises(MT5UnavailableError):
            MT5Broker()


if __name__ == "__main__":
    unittest.main()
