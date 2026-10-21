import unittest
from greeting import greet


class GreetingTests(unittest.TestCase):
    def test_existing_behavior(self):
        self.assertEqual(greet("Alice"), "Hello, Alice!")


if __name__ == "__main__":
    unittest.main()
