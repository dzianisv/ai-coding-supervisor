import unittest
from factorial import factorial


class TestFactorial(unittest.TestCase):
    
    def test_factorial_zero(self):
        """Test factorial of 0"""
        self.assertEqual(factorial(0), 1)
    
    def test_factorial_one(self):
        """Test factorial of 1"""
        self.assertEqual(factorial(1), 1)
    
    def test_factorial_small_numbers(self):
        """Test factorial of small positive numbers"""
        self.assertEqual(factorial(2), 2)
        self.assertEqual(factorial(3), 6)
        self.assertEqual(factorial(4), 24)
        self.assertEqual(factorial(5), 120)
    
    def test_factorial_larger_numbers(self):
        """Test factorial of larger numbers"""
        self.assertEqual(factorial(6), 720)
        self.assertEqual(factorial(7), 5040)
        self.assertEqual(factorial(10), 3628800)
    
    def test_factorial_negative_number(self):
        """Test that factorial raises ValueError for negative numbers"""
        with self.assertRaises(ValueError):
            factorial(-1)
        with self.assertRaises(ValueError):
            factorial(-5)
    
    def test_factorial_non_integer(self):
        """Test that factorial raises TypeError for non-integer inputs"""
        with self.assertRaises(TypeError):
            factorial(3.5)
        with self.assertRaises(TypeError):
            factorial("5")
        with self.assertRaises(TypeError):
            factorial([5])
        with self.assertRaises(TypeError):
            factorial(None)


if __name__ == '__main__':
    unittest.main()