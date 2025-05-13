"""Test cases for Calculator.evaluate method using unittest."""

import unittest

from toolregistry.hub import Calculator


class TestEvaluate(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(Calculator.evaluate("2 + 3 * 4"), 14)
        self.assertEqual(Calculator.evaluate("(2 + 3) * 4"), 20)
        self.assertEqual(Calculator.evaluate("10 / 2"), 5)

    def test_calculator_methods(self):
        self.assertEqual(Calculator.evaluate("sqrt(16)"), 4)
        self.assertEqual(Calculator.evaluate("pow(2, 5)"), 32)
        self.assertEqual(Calculator.evaluate("average([1, 2, 3, 4])"), 2.5)
        self.assertGreater(
            Calculator.evaluate("compound_interest(1000, 0.05, 5, 12)"), 1000
        )

    def test_return_types(self):
        # Test that evaluate can return float, int, and bool
        result_float = Calculator.evaluate("sqrt(25)")
        self.assertIsInstance(result_float, (float, int))
        self.assertEqual(result_float, 5)

        result_int = Calculator.evaluate("floor(3.7)")
        self.assertIsInstance(result_int, int)
        self.assertEqual(result_int, 3)

        result_bool = Calculator.evaluate("isclose(0.1 + 0.2, 0.3)")
        self.assertIsInstance(result_bool, bool)
        self.assertTrue(result_bool)

    def test_combined_expressions(self):
        expr = "average([1,2,3]) + sqrt(pow(2,4))"
        self.assertEqual(Calculator.evaluate(expr), 6.0)

        expr = "gcd(36, 48) + lcm(6, 8)"
        self.assertEqual(Calculator.evaluate(expr), 36)

    def test_error_handling(self):
        with self.assertRaises(ValueError):
            Calculator.evaluate("1 / 0")

        with self.assertRaises(ValueError):
            Calculator.evaluate("sqrt(-1)")

        with self.assertRaises(ValueError):
            Calculator.evaluate("invalid_function(1)")

    def test_builtins_and_extra_operations(self):
        # Test built-in functions provided in evaluate
        self.assertEqual(Calculator.evaluate("abs(-5)"), 5)
        self.assertEqual(Calculator.evaluate("round(3.14159, 2)"), 3.14)
        # min and max expect a single iterable argument, so use list
        self.assertEqual(Calculator.evaluate("min([3, 1, 2])"), 1)
        self.assertEqual(Calculator.evaluate("max([3, 1, 2])"), 3)
        self.assertEqual(Calculator.evaluate("sum([1,2,3])"), 6)
        # len is not supported in evaluate, test separately
        self.assertEqual(len([1, 2, 3, 4]), 4)

    def test_arithmetic_operations(self):
        # Test add, subtract, multiply, divide operations
        self.assertEqual(Calculator.evaluate("add(2,3)"), 5)
        self.assertEqual(Calculator.evaluate("subtract(10,4)"), 6)
        self.assertEqual(Calculator.evaluate("multiply(3,4)"), 12)
        self.assertEqual(Calculator.evaluate("divide(10,2)"), 5)

    def test_scientific_operations(self):
        # Test power, sqrt, trigonometric, and logarithmic functions
        self.assertEqual(Calculator.evaluate("pow(2,3)"), 8)
        self.assertEqual(Calculator.evaluate("sqrt(9)"), 3)
        self.assertEqual(Calculator.evaluate("sin(0)"), 0)
        self.assertAlmostEqual(Calculator.evaluate("cos(0)"), 1, places=5)
        self.assertEqual(Calculator.evaluate("tan(0)"), 0)
        self.assertEqual(Calculator.evaluate("asin(0)"), 0)
        self.assertEqual(Calculator.evaluate("acos(1)"), 0)
        self.assertEqual(Calculator.evaluate("atan(0)"), 0)
        self.assertEqual(Calculator.evaluate("log(100,10)"), 2)
        import math

        self.assertAlmostEqual(Calculator.evaluate(f"ln({math.e})"), 1, places=5)
        self.assertEqual(Calculator.evaluate("log10(100)"), 2)
        self.assertEqual(Calculator.evaluate("log2(8)"), 3)

    def test_other_math_operations(self):
        # Test mod, factorial, round, floor, ceil, gcd, lcm operations
        self.assertEqual(Calculator.evaluate("mod(10,3)"), 1)
        self.assertEqual(Calculator.evaluate("factorial(5)"), 120)
        self.assertEqual(Calculator.evaluate("round(3.6)"), 4)
        self.assertEqual(Calculator.evaluate("floor(3.9)"), 3)
        self.assertEqual(Calculator.evaluate("ceil(3.1)"), 4)
        self.assertEqual(Calculator.evaluate("gcd(12,18)"), 6)
        self.assertEqual(Calculator.evaluate("lcm(3,4)"), 12)

    def test_statistical_functions(self):
        # Test average, median, mode, standard_deviation functions
        self.assertEqual(Calculator.evaluate("average([1,2,3,4,5])"), 3)
        self.assertEqual(Calculator.evaluate("median([1,2,3,4,5])"), 3)
        self.assertEqual(Calculator.evaluate("mode([1,2,2,3])"), [2])
        # Standard deviation for [1,2,3] is approximately sqrt((1+0+1)/3) = sqrt(0.6667)
        self.assertAlmostEqual(
            Calculator.evaluate("standard_deviation([1,2,3])"), 0.8164965809, places=5
        )

    def test_financial_functions(self):
        # Test simple_interest and compound_interest functions
        self.assertEqual(Calculator.evaluate("simple_interest(1000,0.05,3)"), 150)
        self.assertAlmostEqual(
            Calculator.evaluate("compound_interest(1000,0.05,3,1)"), 1157.625, places=3
        )

    def test_distance_and_norm(self):
        # Test dist and norm_euclidean functions
        self.assertEqual(Calculator.evaluate("dist([0,0], [3,4], 'euclidean')"), 5)
        self.assertEqual(Calculator.evaluate("dist([0,0], [3,4], 'manhattan')"), 7)
        self.assertEqual(Calculator.evaluate("norm_euclidean([3,4])"), 5)

        # Test error cases
        with self.assertRaises(ValueError):
            Calculator.evaluate("dist([0,0], [3,4,5], 'euclidean')")

    def test_cbrt_function(self):
        # Test cube root function
        self.assertEqual(Calculator.evaluate("cbrt(8)"), 2)
        self.assertEqual(Calculator.evaluate("cbrt(-27)"), -3)
        self.assertAlmostEqual(Calculator.evaluate("cbrt(10)"), 2.15443469003, places=5)

    def test_help_and_allowed_functions(self):
        # Test help documentation and allowed functions list
        help_text = Calculator.help("sqrt")
        self.assertIn("square root of a number", help_text)

        allowed_fns = Calculator.allowed_fns_in_evaluate()
        self.assertIn("sqrt", allowed_fns)
        self.assertIn("add", allowed_fns)
        self.assertNotIn("eval", allowed_fns)
