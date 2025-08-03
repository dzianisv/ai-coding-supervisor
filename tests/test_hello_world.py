#!/usr/bin/env python3
"""
Tests for the hello_world.py script
"""

import io
import sys
from unittest.mock import patch
import pytest

from hello_world import main


class TestHelloWorld:
    """Test class for hello world functionality"""
    
    @pytest.mark.unit
    def test_main_prints_hello_world(self):
        """Test that main() prints 'Hello, world!'"""
        # Capture stdout
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            main()
        
        # Verify the output
        output = captured_output.getvalue().strip()
        assert output == "Hello, world!"
    
    @pytest.mark.unit 
    def test_main_function_exists(self):
        """Test that main function exists and is callable"""
        assert callable(main)
    
    @pytest.mark.unit
    def test_script_can_be_imported(self):
        """Test that the hello_world module can be imported"""
        import hello_world
        assert hasattr(hello_world, 'main')