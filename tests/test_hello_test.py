#!/usr/bin/env python3
"""
Tests for hello_test.py
"""

import unittest
import sys
from io import StringIO
from hello_test import main

class TestHelloTest(unittest.TestCase):
    """Test cases for hello_test module."""
    
    def test_main_prints_hello_world(self):
        """Test that main() prints 'Hello, World!'"""
        captured_output = StringIO()
        sys.stdout = captured_output
        
        main()
        
        sys.stdout = sys.__stdout__
        self.assertEqual(captured_output.getvalue().strip(), "Hello, World!")
    
    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        self.assertTrue(callable(main))

if __name__ == "__main__":
    unittest.main()