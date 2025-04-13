"""Calculator module providing mathematical calculation functions.

This module contains the Calculator class and convenience functions for:
- Basic arithmetic: add, subtract, multiply, divide
- Scientific operations: power, square root, trigonometric, logarithmic (log, ln, log10, log2)
- Statistical functions: average, median, mode, standard_deviation
- Financial calculations: simple/compound interest
- Random number generation
- Unit conversions
- Expression evaluation

Example:
    >>> from toolregistry.hub import Calculator
    >>> calc = Calculator()
    >>> calc.add(1, 2)
    3
    >>> calc.evaluate("2 * (3 + 4)")
    14
"""

import math
import random
from typing import Dict, List


class Calculator:
    """Performs mathematical calculations.

    Attributes:
        None

    Methods:
        Basic arithmetic:
            add, subtract, multiply, divide
        Scientific operations:
            power, sqrt, sin, cos, tan, asin, acos, atan,
            log, ln, log10, mod, abs, factorial, round, floor, ceil
        Statistical functions:
            average, median, mode, standard_deviation
        Financial calculations:
            simple_interest, compound_interest
        Random number generation:
            random, randint
        Unit conversions:
            celsius_to_fahrenheit, fahrenheit_to_celsius
        Expression evaluation:
            evaluate
    """

    @staticmethod
    def add(a: float, b: float) -> float:
        """Adds two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Sum of a and b
        """
        return a + b

    @staticmethod
    def subtract(a: float, b: float) -> float:
        """Subtracts two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Difference between a and b
        """
        return a - b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        """Multiplies two numbers.

        Args:
            a: First number
            b: Second number

        Returns:
            Product of a and b
        """
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        """Divides two numbers.

        Args:
            a: Numerator
            b: Denominator

        Returns:
            Quotient of a divided by b

        Raises:
            ValueError: If b is zero
        """
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @staticmethod
    def power(base: float, exponent: float) -> float:
        """Raises base to exponent power.

        Args:
            base: The base number
            exponent: The exponent

        Returns:
            base raised to exponent
        """
        return base**exponent

    @staticmethod
    def sqrt(x: float) -> float:
        """Calculates square root of a number.

        Args:
            x: Number to take square root of

        Returns:
            Square root of x

        Raises:
            ValueError: If x is negative
        """
        if x < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return x**0.5

    @staticmethod
    def evaluate(expression: str) -> float:
        """Evaluates a mathematical expression string.

        Args:
            expression (str): String containing mathematical expression

        Returns:
            float: Result of evaluated expression

        Raises:
            ValueError: If expression is invalid
        """
        try:
            return eval(expression, {"__builtins__": None}, {})
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    # Trigonometric functions
    @staticmethod
    def sin(x: float) -> float:
        """Calculates sine of x (in radians).

        Args:
            x (float): Angle in radians

        Returns:
            float: Sine of x
        """
        return math.sin(x)

    @staticmethod
    def cos(x: float) -> float:
        """Calculates cosine of x (in radians).

        Args:
            x (float): Angle in radians

        Returns:
            float: Cosine of x
        """
        return math.cos(x)

    @staticmethod
    def tan(x: float) -> float:
        """Calculates tangent of x (in radians).

        Args:
            x (float): Angle in radians

        Returns:
            float: Tangent of x
        """
        return math.tan(x)

    @staticmethod
    def asin(x: float) -> float:
        """Calculates arcsine of x in radians.

        Args:
            x (float): Value between -1 and 1

        Returns:
            float: Angle in radians

        Raises:
            ValueError: If x is outside [-1, 1]
        """
        if x < -1 or x > 1:
            raise ValueError("x must be between -1 and 1")
        return math.asin(x)

    @staticmethod
    def acos(x: float) -> float:
        """Calculates arccosine of x in radians.

        Args:
            x (float): Value between -1 and 1

        Returns:
            float: Angle in radians

        Raises:
            ValueError: If x is outside [-1, 1]
        """
        if x < -1 or x > 1:
            raise ValueError("x must be between -1 and 1")
        return math.acos(x)

    @staticmethod
    def atan(x: float) -> float:
        """Calculates arctangent of x in radians.

        Args:
            x (float): Any real number

        Returns:
            float: Angle in radians
        """
        return math.atan(x)

    # Logarithmic functions
    @staticmethod
    def log(x: float, base: float = 10) -> float:
        """Calculates logarithm of x with given base.

        Args:
            x (float): Positive number
            base (float, optional): Logarithm base. Defaults to 10.

        Returns:
            float: Logarithm of x with given base

        Raises:
            ValueError: If x <= 0 or base <= 0 or base == 1
        """
        if x <= 0:
            raise ValueError("x must be positive")
        if base <= 0 or base == 1:
            raise ValueError("base must be positive and not equal to 1")
        return math.log(x, base)

    @staticmethod
    def ln(x: float) -> float:
        """Calculates natural logarithm (base e) of x.

        Args:
            x (float): Positive number

        Returns:
            float: Natural logarithm of x

        Raises:
            ValueError: If x <= 0
        """
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log(x)

    @staticmethod
    def log10(x: float) -> float:
        """Calculates base-10 logarithm of x.

        Args:
            x (float): Positive number

        Returns:
            float: Base-10 logarithm of x

        Raises:
            ValueError: If x <= 0
        """
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log10(x)

    @staticmethod
    def log2(x: float) -> float:
        """Calculates base-2 logarithm of x.

        Args:
            x (float): Positive number

        Returns:
            float: Base-2 logarithm of x

        Raises:
            ValueError: If x <= 0
        """
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log2(x)

    # Other math operations
    @staticmethod
    def mod(a: float, b: float) -> float:
        """Calculates a modulo b.

        Args:
            a (float): Dividend
            b (float): Divisor

        Returns:
            float: Remainder of a divided by b

        Raises:
            ValueError: If b is zero
        """
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a % b

    @staticmethod
    def abs(x: float) -> float:
        """Calculates absolute value of x.

        Args:
            x (float): Any number

        Returns:
            float: Absolute value of x
        """
        return abs(x)

    @staticmethod
    def factorial(n: int) -> int:
        """Calculates factorial of n.

        Args:
            n (int): Non-negative integer

        Returns:
            int: Factorial of n

        Raises:
            ValueError: If n is negative
        """
        if n < 0:
            raise ValueError("n must be non-negative")
        return math.factorial(n)

    @staticmethod
    def round(x: float, digits: int = 0) -> float:
        """Rounds x to given number of decimal digits.

        Args:
            x (float): Number to round
            digits (int, optional): Number of decimal places. Defaults to 0.

        Returns:
            float: Rounded number
        """
        return round(x, digits)

    @staticmethod
    def floor(x: float) -> int:
        """Rounds x down to nearest integer.

        Args:
            x (float): Number to round down

        Returns:
            int: Largest integer <= x
        """
        return math.floor(x)

    @staticmethod
    def ceil(x: float) -> int:
        """Rounds x up to nearest integer.

        Args:
            x (float): Number to round up

        Returns:
            int: Smallest integer >= x
        """
        return math.ceil(x)

    @staticmethod
    def gcd(a: int, b: int) -> int:
        """Calculates greatest common divisor of a and b.

        Args:
            a (int): First number
            b (int): Second number

        Returns:
            int: GCD of a and b
        """
        return math.gcd(a, b)

    @staticmethod
    def lcm(a: int, b: int) -> int:
        """Calculates least common multiple of a and b.

        Args:
            a (int): First number
            b (int): Second number

        Returns:
            int: LCM of a and b
        """
        return abs(a * b) // math.gcd(a, b) if a and b else 0

    # Statistical functions
    @staticmethod
    def average(numbers: List[float]) -> float:
        """Calculates arithmetic mean of numbers.

        Args:
            numbers (List[float]): List of numbers

        Returns:
            float: Average value

        Raises:
            ValueError: If numbers list is empty
        """
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        return sum(numbers) / len(numbers)

    @staticmethod
    def median(numbers: List[float]) -> float:
        """Calculates median of numbers.

        Args:
            numbers (List[float]): List of numbers

        Returns:
            float: Median value

        Raises:
            ValueError: If numbers list is empty
        """
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        sorted_numbers = sorted(numbers)
        n = len(sorted_numbers)
        mid = n // 2
        if n % 2 == 1:
            return sorted_numbers[mid]
        return (sorted_numbers[mid - 1] + sorted_numbers[mid]) / 2

    @staticmethod
    def mode(numbers: List[float]) -> List[float]:
        """Finds mode(s) of numbers.

        Args:
            numbers (List[float]): List of numbers

        Returns:
            List[float]: List of mode values

        Raises:
            ValueError: If numbers list is empty
        """
        if not numbers:
            raise ValueError("numbers list cannot be empty")

        freq: Dict[float, int] = {}
        for num in numbers:
            freq[num] = freq.get(num, 0) + 1
        max_count = max(freq.values())
        return [num for num, count in freq.items() if count == max_count]

    @staticmethod
    def standard_deviation(numbers: List[float]) -> float:
        """Calculates population standard deviation of numbers.

        Args:
            numbers (List[float]): List of numbers

        Returns:
            float: Standard deviation

        Raises:
            ValueError: If numbers list is empty
        """
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        mean = Calculator.average(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return math.sqrt(variance)

    # Financial calculations
    @staticmethod
    def simple_interest(principal: float, rate: float, time: float) -> float:
        """Calculates simple interest.

        Args:
            principal (float): Initial amount
            rate (float): Annual interest rate (decimal)
            time (float): Time in years

        Returns:
            float: Simple interest amount
        """
        return principal * rate * time

    @staticmethod
    def compound_interest(
        principal: float, rate: float, time: float, periods: int = 1
    ) -> float:
        """Calculates compound interest.

        Args:
            principal (float): Initial amount
            rate (float): Annual interest rate (decimal)
            time (float): Time in years
            periods (int, optional): Compounding periods per year. Defaults to 1.

        Returns:
            float: Final amount after compounding
        """
        return principal * (1 + rate / periods) ** (periods * time)

    # Random number generation
    @staticmethod
    def random() -> float:
        """Generates random float between 0 and 1.

        Returns:
            float: Random number in [0, 1)
        """
        return random.random()

    @staticmethod
    def randint(a: int, b: int) -> int:
        """Generates random integer between a and b (inclusive).

        Args:
            a (int): Lower bound
            b (int): Upper bound

        Returns:
            int: Random integer in [a, b]

        Raises:
            ValueError: If a > b
        """
        if a > b:
            raise ValueError("a must be <= b")
        return random.randint(a, b)
