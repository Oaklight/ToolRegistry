"""Calculator module providing mathematical calculation functions.

This module contains the Calculator class which provides a comprehensive set of mathematical operations including:

- Constants: pi, e, tau, inf, nan
- Basic arithmetic: add, subtract, multiply, divide, mod
- Power and roots: power, sqrt, cbrt, isqrt
- Distance and norm: dist, hypot
- Trigonometric functions: sin, cos, tan, asin, acos, atan, degrees, radians
- Hyperbolic functions: sinh, cosh, tanh, asinh, acosh, atanh
- Logarithmic and exponential functions: log, ln, log10, log2, log1p, exp, expm1
- Numerical processing: abs, round, floor, ceil, trunc, copysign, frexp, ldexp, modf, remainder, nextafter, ulp, fmod, isclose
- Combinatorics: factorial, gcd, lcm, comb, perm
- Special functions: erf, erfc, gamma, lgamma
- Numerical validation: isfinite, isinf, isnan
- Statistical functions: average, median, mode, standard_deviation, min, max, sum, prod, fsum
- Financial calculations: simple_interest, compound_interest
- Random number generation: random, randint
- Expression evaluation: evaluate (supports expressions combining above functions)

Example:
    >>> from toolregistry.hub import Calculator
    >>> calc = Calculator()
    >>> calc.add(1, 2)
    3
    >>> calc.evaluate("add(2, 3) * power(2, 3) + sqrt(16)")
    44
"""

import math
import random
import sys
from typing import Dict, List, Union


class Calculator:
    """Performs mathematical calculations.

    This class provides a unified interface for a wide range of mathematical operations,
    including basic arithmetic, scientific functions, statistical calculations,
    financial computations, random number generation, and expression evaluation.

    Methods:
        Constants:
            pi, e, tau, inf, nan
        Basic arithmetic:
            add, subtract, multiply, divide, mod
        Power and roots:
            power, sqrt, cbrt, isqrt
        Distance and norm:
            dist, hypot
        Trigonometric functions:
            sin, cos, tan, asin, acos, atan, degrees, radians
        Hyperbolic functions:
            sinh, cosh, tanh, asinh, acosh, atanh
        Logarithmic and exponential functions:
            log, ln, log10, log2, log1p, exp, expm1
        Numerical processing:
            abs, round, floor, ceil, trunc, copysign, frexp, ldexp, modf, remainder, nextafter, ulp, fmod, isclose
        Combinatorics:
            factorial, gcd, lcm, comb, perm
        Special functions:
            erf, erfc, gamma, lgamma
        Numerical validation:
            isfinite, isinf, isnan
        Statistical functions:
            average, median, mode, standard_deviation, min, max, sum, prod, fsum
        Financial calculations:
            simple_interest, compound_interest
        Random number generation:
            random, randint
        Expression evaluation:
            evaluate
    """

    # ====== Constant 常数定义 ======
    @staticmethod
    def pi() -> float:
        """Returns the mathematical constant π."""
        return math.pi

    @staticmethod
    def e() -> float:
        """Returns the mathematical constant e."""
        return math.e

    @staticmethod
    def tau() -> float:
        """Returns the mathematical constant tau (2π)."""
        return math.tau

    @staticmethod
    def inf() -> float:
        """Returns positive infinity."""
        return math.inf

    @staticmethod
    def nan() -> float:
        """Returns NaN (Not a Number)."""
        return math.nan

    # ====== Basic arithmetic 基本算术运算 ======
    @staticmethod
    def add(a: float, b: float) -> float:
        """Adds two numbers."""
        return a + b

    @staticmethod
    def subtract(a: float, b: float) -> float:
        """Subtracts two numbers."""
        return a - b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        """Multiplies two numbers."""
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        """Divides two numbers."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @staticmethod
    def mod(a: float, b: float) -> float:
        """Calculates a modulo b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a % b

    # ====== Power and roots 幂和根 ======
    @staticmethod
    def power(base: float, exponent: float) -> float:
        """Raises base to exponent power."""
        # No range check needed for power
        return base**exponent

    @staticmethod
    def sqrt(x: float) -> float:
        """Calculates square root of a number."""
        if x < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return x**0.5

    @staticmethod
    def cbrt(x: float) -> float:
        """Calculates cube root of a number."""
        return math.copysign(abs(x) ** (1 / 3), x)

    @staticmethod
    def isqrt(n: int) -> int:
        """Calculates integer square root of non-negative integer n."""
        if n < 0:
            raise ValueError("n must be non-negative")
        return math.isqrt(n)

    # ====== Distance and norm 距离/范数 ======
    @staticmethod
    def dist(p: List[float], q: List[float]) -> float:
        """Calculates Euclidean distance between two points."""
        if len(p) != len(q):
            raise ValueError("Points must have same dimensions")
        return math.dist(p, q)

    @staticmethod
    def hypot(*coordinates: float) -> float:
        """Calculates Euclidean norm (sqrt(sum(x^2)))."""
        return math.hypot(*coordinates)

    # ====== Trignormetric functions 三角函数 ======
    @staticmethod
    def sin(x: float) -> float:
        """Calculates sine of x (in radians)."""
        # No range check needed for sin
        return math.sin(x)

    @staticmethod
    def cos(x: float) -> float:
        """Calculates cosine of x (in radians)."""
        # No range check needed for cos
        return math.cos(x)

    @staticmethod
    def tan(x: float) -> float:
        """Calculates tangent of x (in radians)."""
        # No range check needed for tan
        return math.tan(x)

    @staticmethod
    def asin(x: float) -> float:
        """Calculates arcsine of x (in radians)."""
        if x < -1 or x > 1:
            raise ValueError("x must be between -1 and 1")
        return math.asin(x)

    @staticmethod
    def acos(x: float) -> float:
        """Calculates arccosine of x (in radians)."""
        if x < -1 or x > 1:
            raise ValueError("x must be between -1 and 1")
        return math.acos(x)

    @staticmethod
    def atan(x: float) -> float:
        """Calculates arctangent of x (in radians)."""
        # No range check needed for atan
        return math.atan(x)

    @staticmethod
    def degrees(x: float) -> float:
        """Converts angle x from radians to degrees."""
        # No range check needed for degrees
        return math.degrees(x)

    @staticmethod
    def radians(x: float) -> float:
        """Converts angle x from degrees to radians."""
        # No range check needed for radians
        return math.radians(x)

    # ====== Hyperbolic functions 双曲函数 ======
    @staticmethod
    def sinh(x: float) -> float:
        """Calculates the hyperbolic sine of x."""
        # No range check needed for sinh
        return math.sinh(x)

    @staticmethod
    def cosh(x: float) -> float:
        """Calculates the hyperbolic cosine of x."""
        # No range check needed for cosh
        return math.cosh(x)

    @staticmethod
    def tanh(x: float) -> float:
        """Calculates the hyperbolic tangent of x."""
        # No range check needed for tanh
        return math.tanh(x)

    @staticmethod
    def asinh(x: float) -> float:
        """Calculates the inverse hyperbolic sine of x."""
        # No range check needed for asinh
        return math.asinh(x)

    @staticmethod
    def acosh(x: float) -> float:
        """Calculates the inverse hyperbolic cosine of x. x must be >= 1."""
        if x < 1:
            raise ValueError("x must be >= 1 for acosh")
        return math.acosh(x)

    @staticmethod
    def atanh(x: float) -> float:
        """Calculates the inverse hyperbolic tangent of x. |x| must be less than 1."""
        if abs(x) >= 1:
            raise ValueError("Absolute value of x must be less than 1 for atanh")
        return math.atanh(x)

    # ====== Logarithmic and exponential functions 对数/指数函数 ======
    @staticmethod
    def log(x: float, base: float = 10) -> float:
        """Calculates logarithm of x with given base."""
        if x <= 0:
            raise ValueError("x must be positive")
        if base <= 0 or base == 1:
            raise ValueError("base must be positive and not equal to 1")
        return math.log(x, base)

    @staticmethod
    def ln(x: float) -> float:
        """Calculates natural (base-e) logarithm of x."""
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log(x)

    @staticmethod
    def log10(x: float) -> float:
        """Calculates base-10 logarithm of x."""
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log10(x)

    @staticmethod
    def log2(x: float) -> float:
        """Calculates base-2 logarithm of x."""
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log2(x)

    @staticmethod
    def log1p(x: float) -> float:
        """Calculates the natural logarithm of 1+x."""
        if x <= -1:
            raise ValueError("x must be greater than -1")
        return math.log1p(x)

    @staticmethod
    def exp(x: float) -> float:
        """Calculates the exponential of x (e^x)."""
        # No range check needed for exp
        return math.exp(x)

    @staticmethod
    def expm1(x: float) -> float:
        """Calculates e^x - 1 accurately for small x."""
        # No range check needed for expm1
        return math.expm1(x)

    # ====== Numerical Processing 数值处理 ======
    @staticmethod
    def abs(x: float) -> float:
        """Calculates absolute value of x."""
        # No range check needed for abs
        return abs(x)

    @staticmethod
    def round(x: float, digits: int = 0) -> float:
        """Rounds x to given number of decimal digits."""
        # No range check needed for round
        return round(x, digits)

    @staticmethod
    def floor(x: float) -> int:
        """Rounds x down to nearest integer."""
        # No range check needed for floor
        return math.floor(x)

    @staticmethod
    def ceil(x: float) -> int:
        """Rounds x up to nearest integer."""
        # No range check needed for ceil
        return math.ceil(x)

    @staticmethod
    def trunc(x: float) -> int:
        """Truncates x by removing the fractional part."""
        # No range check needed for trunc
        return math.trunc(x)

    @staticmethod
    def copysign(a: float, b: float) -> float:
        """Returns a float with the magnitude of a but the sign of b."""
        # No range check needed for copysign
        return math.copysign(a, b)

    @staticmethod
    def frexp(x: float):
        """Returns the mantissa and exponent of x as the pair (m, e)."""
        # No range check needed for frexp
        return math.frexp(x)

    @staticmethod
    def ldexp(x: float, i: int) -> float:
        """Returns x * (2**i) computed exactly."""
        # No range check needed for ldexp
        return math.ldexp(x, i)

    @staticmethod
    def modf(x: float):
        """Returns the fractional and integer parts of x."""
        # No range check needed for modf
        return math.modf(x)

    @staticmethod
    def remainder(x: float, y: float) -> float:
        """Returns IEEE 754-style remainder of x/y."""
        return math.remainder(x, y)

    @staticmethod
    def nextafter(x: float, y: float) -> float:
        """Returns next floating-point value after x towards y.

        Raises:
            NotImplementedError: If Python version is lower than 3.9
        """
        if sys.version_info < (3, 9):
            raise NotImplementedError("nextafter requires Python 3.9 or higher")
        return math.nextafter(x, y)

    @staticmethod
    def ulp(x: float) -> float:
        """Returns the value of the least significant bit of x.

        Raises:
            NotImplementedError: If Python version is lower than 3.9
        """
        if sys.version_info < (3, 9):
            raise NotImplementedError("ulp requires Python 3.9 or higher")
        return math.ulp(x)

    @staticmethod
    def fmod(x: float, y: float) -> float:
        """Returns floating-point remainder of x/y."""
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return math.fmod(x, y)

    @staticmethod
    def isclose(
        a: float, b: float, rel_tol: float = 1e-09, abs_tol: float = 0.0
    ) -> bool:
        """Determines whether two floats are close in value."""
        # No range check needed for isclose
        return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)

    # ====== Combinatorics 组合数学 ======
    @staticmethod
    def factorial(n: int) -> int:
        """Calculates factorial of n."""
        if n < 0:
            raise ValueError("n must be non-negative")
        return math.factorial(n)

    @staticmethod
    def gcd(a: int, b: int) -> int:
        """Calculates greatest common divisor of a and b."""
        # No range check needed for gcd
        return math.gcd(a, b)

    @staticmethod
    def lcm(a: int, b: int) -> int:
        """Calculates least common multiple of a and b."""
        # No range check needed for lcm
        return abs(a * b) // math.gcd(a, b) if a and b else 0

    @staticmethod
    def comb(n: int, k: int) -> int:
        """Calculates the number of combinations (n choose k)."""
        # No range check needed for comb
        return math.comb(n, k)

    @staticmethod
    def perm(n: int, k: int) -> int:
        """Calculates the number of permutations of n items taken k at a time."""
        # No range check needed for perm
        return math.perm(n, k)

    # ====== Special Functions 特殊数学函数 ======
    @staticmethod
    def erf(x: float) -> float:
        """Calculates the error function of x."""
        # No range check needed for erf
        return math.erf(x)

    @staticmethod
    def erfc(x: float) -> float:
        """Calculates the complementary error function of x."""
        # No range check needed for erfc
        return math.erfc(x)

    @staticmethod
    def gamma(x: float) -> float:
        """Calculates the Gamma function of x."""
        # No range check needed for gamma
        return math.gamma(x)

    @staticmethod
    def lgamma(x: float) -> float:
        """Calculates the natural logarithm of the absolute value of the Gamma function of x."""
        # No range check needed for lgamma
        return math.lgamma(x)

    # ====== Numerical Validation 数值检查 ======
    @staticmethod
    def isfinite(x: float) -> bool:
        """Checks if x is finite."""
        # No range check needed for isfinite
        return math.isfinite(x)

    @staticmethod
    def isinf(x: float) -> bool:
        """Checks if x is infinite."""
        # No range check needed for isinf
        return math.isinf(x)

    @staticmethod
    def isnan(x: float) -> bool:
        """Checks if x is NaN."""
        # No range check needed for isnan
        return math.isnan(x)

    # ====== Statistical functions 统计函数 ======
    @staticmethod
    def average(numbers: List[float]) -> float:
        """Calculates arithmetic mean of numbers."""
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        return sum(numbers) / len(numbers)

    @staticmethod
    def median(numbers: List[float]) -> float:
        """Calculates median of numbers."""
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
        """Finds mode(s) of numbers."""
        if not numbers:
            raise ValueError("numbers list cannot be empty")

        freq: Dict[float, int] = {}
        for num in numbers:
            freq[num] = freq.get(num, 0) + 1
        max_count = max(freq.values())
        return [num for num, count in freq.items() if count == max_count]

    @staticmethod
    def standard_deviation(numbers: List[float]) -> float:
        """Calculates population standard deviation of numbers."""
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        mean = Calculator.average(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return math.sqrt(variance)

    @staticmethod
    def min(numbers: List[float]) -> float:
        """Finds the minimum value in a list of numbers."""
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        return min(numbers)

    @staticmethod
    def max(numbers: List[float]) -> float:
        """Finds the maximum value in a list of numbers."""
        if not numbers:
            raise ValueError("numbers list cannot be empty")
        return max(numbers)

    @staticmethod
    def sum(numbers: List[float]) -> float:
        """Calculates the sum of a list of numbers."""
        # No range check needed for sum
        return sum(numbers)

    @staticmethod
    def prod(numbers: List[float]) -> float:
        """Calculates the product of a list of numbers."""
        # No range check needed for prod
        return math.prod(numbers)

    @staticmethod
    def fsum(numbers: List[float]) -> float:
        """Calculates an accurate floating point sum of numbers."""
        # No range check needed for fsum
        return math.fsum(numbers)

    # ====== Financial calculations 金融计算 ======
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
        # No range check needed for simple_interest
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
        # No range check needed for compound_interest
        return principal * (1 + rate / periods) ** (periods * time)

    # ====== Random number generation 随机数生成 ======
    @staticmethod
    def random() -> float:
        """Generates random float between 0 and 1."""
        # No range check needed for random
        return random.random()

    @staticmethod
    def randint(a: int, b: int) -> int:
        """Generates random integer between a and b."""
        if a > b:
            raise ValueError("a must be <= b")
        return random.randint(a, b)

    # ====== Expression evaluation 表达式求值 ======
    @staticmethod
    def evaluate(expression: str) -> Union[float, int, bool]:
        """Evaluates a mathematical expression using a unified interface.

        This method is intended for complex expressions that combine two or more operations.
        For simple, single-step operations, please directly use the corresponding static method (e.g., add, subtract).

        The evaluate method supports the following operations:
            - Constants: pi, e, tau, inf, nan
            - Basic arithmetic: add, subtract, multiply, divide, mod
            - Power and roots: power, sqrt, cbrt, isqrt
            - Distance and norm: dist, hypot
            - Trigonometric functions: sin, cos, tan, asin, acos, atan, degrees, radians
            - Hyperbolic functions: sinh, cosh, tanh, asinh, acosh, atanh
            - Logarithmic and exponential functions: log, ln, log10, log2, log1p, exp, expm1
            - Numerical processing: abs, round, floor, ceil, trunc, copysign, frexp, ldexp, modf, remainder, nextafter, ulp, fmod, isclose
            - Combinatorics: factorial, gcd, lcm, comb, perm
            - Special functions: erf, erfc, gamma, lgamma
            - Numerical validation: isfinite, isinf, isnan
            - Statistical functions: average, median, mode, standard_deviation, min, max, sum, prod, fsum
            - Financial calculations: simple_interest, compound_interest
            - Random number generation: random, randint

        The expression should be a valid Python expression utilizing the above functions.
        For example: "add(2, 3) * power(2, 3) + sqrt(16)".

        Args:
            expression (str): Mathematical expression to evaluate.

        Returns:
            Union[float, int, bool]: The result of the evaluated expression.

        Raises:
            ValueError: If the expression is invalid or its evaluation fails.
        """
        # Get all static methods from Calculator class using __dict__,
        # excluding 'evaluate' to avoid redundancy.
        allowed_functions = {
            name: func.__func__
            for name, func in Calculator.__dict__.items()
            if isinstance(func, staticmethod) and name not in ("evaluate")
        }
        allowed_functions.update(
            {
                "pow": Calculator.power,
            }
        )
        # Add basic builtins

        try:
            return eval(expression, {"__builtins__": None}, allowed_functions)
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")
