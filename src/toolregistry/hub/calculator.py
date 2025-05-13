import inspect
import math
import textwrap
from typing import Dict, List, Literal, Union

from ..utils import get_all_static_methods


class Calculator:
    """Performs mathematical calculations.

    This class provides a unified interface for a wide range of mathematical operations,
    including basic arithmetic, scientific functions, statistical calculations,
    financial computations, random number generation, and expression evaluation.

    Methods:
        Basic arithmetic:
            add, subtract, multiply, divide, mod
        Numerical processing:
            abs, round
        Power and roots:
            pow, sqrt, cbrt
        Logarithmic and exponential functions:
            log, ln, exp
        Statistical functions:
            min, max, sum, average, median, mode, standard_deviation
        Combinatorics:
            factorial, gcd, lcm, comb, perm
        Distance and norm:
            dist, dist_manhattan, norm_euclidean
        Financial calculations:
            simple_interest, compound_interest
        Expression evaluation:
            evaluate, allowed_fns_in_evaluate, help
    """

    # ====== Basic arithmetic 基本算术运算 ======
    @staticmethod
    def add(a: float, b: float) -> float:
        """Adds two numbers."""
        return a + b

    @staticmethod
    def subtract(a: float, b: float) -> float:
        """Subtracts b from a."""
        return a - b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        """Multiplies two numbers."""
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        """Divides a by b. b != 0"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @staticmethod
    def mod(a: float, b: float) -> float:
        """Modulo a by b. b != 0"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a % b

    # ====== Numerical processing 数值处理 ======
    @staticmethod
    def abs(x: float) -> float:
        """absolute value of x."""
        # No range check needed for abs
        return abs(x)

    @staticmethod
    def round(x: float, n: int = 0) -> float:
        """Rounds x to n decimal places."""
        return round(x, n)

    # ====== Power and roots 幂和根 ======
    @staticmethod
    def pow(base: float, exponent: float) -> float:
        """Raises base to exponent power."""
        # No range check needed for power
        return math.pow(base, exponent)

    @staticmethod
    def sqrt(x: float) -> float:
        """square root of a number."""
        if x < 0:
            raise ValueError("Cannot calculate square root of negative number")
        return math.sqrt(x)

    @staticmethod
    def cbrt(x: float) -> float:
        """cube root of a number."""
        return math.copysign(abs(x) ** (1 / 3), x)

    # ====== Logarithmic and exponential functions 对数/指数函数 ======
    @staticmethod
    def log(x: float, base: float = 10) -> float:
        """logarithm of x with given base, default base is 10."""
        if x <= 0:
            raise ValueError("x must be positive")
        if base <= 0 or base == 1:
            raise ValueError("base must be positive and not equal to 1")
        return math.log(x, base)

    @staticmethod
    def ln(x: float) -> float:
        """natural (base-e) logarithm of x."""
        if x <= 0:
            raise ValueError("x must be positive")
        return math.log(x)

    @staticmethod
    def exp(x: float) -> float:
        """the exponential of x (e^x)."""
        # No range check needed for exp
        return math.exp(x)

    # ====== Statistical functions 统计函数 ======
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

    # ====== Distance and norm 距离/范数 ======
    @staticmethod
    def dist(
        p: List[float],
        q: List[float],
        metric: Literal["euclidean", "manhattan"] = "euclidean",
    ) -> float:
        """Calculates distance between two points, using specified metric."""
        if len(p) != len(q):
            raise ValueError("Points must have same dimensions")
        if metric == "euclidean":
            return math.dist(p, q)
        else:  # "manhattan"
            return sum(abs(x - y) for x, y in zip(p, q))

    @staticmethod
    def norm_euclidean(p: List[float]) -> float:
        """Calculates Euclidean norm of a point."""
        return math.hypot(*p)  # Using math.hypot for Euclidean norm

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

    # ====== Expression evaluation 表达式求值 ======

    @staticmethod
    def allowed_fns_in_evaluate() -> List[str]:
        """Returns a list of allowed functions for the evaluate method."""

        return _ALLOWED_FUNCTIONS + _MATH_LIB_FUNCTIONS

    @staticmethod
    def help(fn_name: str) -> str:
        """Returns the help documentation for a specific function used in the evaluate method.

        Args:
            fn_name (str): Name of the function to get help for.

        Returns:
            str: Help documentation for the specified function.

        Raises:
            ValueError: If the function name is not recognized.
        """
        # Check if the function is in Calculator or math
        if fn_name not in Calculator.allowed_fns_in_evaluate():
            raise ValueError(f"Function '{fn_name}' is not recognized.")

        # Resolving whether the function is from Calculator or math
        if hasattr(Calculator, fn_name):
            target = getattr(Calculator, fn_name)
        elif hasattr(math, fn_name):  # Handle math functions
            target = getattr(math, fn_name)
        else:
            target = None

        if target is None:
            raise ValueError(f"Function '{fn_name}' cannot be resolved.")

        # Get docstring and function signature
        docstring = inspect.getdoc(target)
        docstring = docstring.strip() if docstring else ""
        signature = inspect.signature(target) if callable(target) else None

        return f"function: {fn_name}{signature}\n{textwrap.indent(docstring, ' ' * 4)}"

    @staticmethod
    def evaluate(expression: str) -> Union[float, int, bool]:
        """Evaluates a mathematical expression using a unified interface.

        This method is intended for complex expressions that combine two or more operations or advanced mathematical functions.
        For simple, single-step operations, please directly use the corresponding static method (e.g., add, subtract).

        The full list of supported functions can be obtained by calling `allowed_fns_in_evaluate()`. Anything beyond this list is not supported. `help` method can be used to get detailed information about each function.

        The `expression` should be a valid Python expression utilizing these functions.
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
            if isinstance(func, staticmethod) and name in _ALLOWED_FUNCTIONS
        }
        # Include math module functions which not already in Calculator class

        allowed_functions.update(
            {name: getattr(math, name) for name in _MATH_LIB_FUNCTIONS}
        )

        try:
            # Allow safe builtins like abs, min, max, round etc
            safe_builtins = {
                "__builtins__": {
                    "int": int,
                    "float": float,
                    "bool": bool,
                }
            }
            return eval(expression, safe_builtins, allowed_functions)
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")


# primarily because they don't have signature or are unsafe
_EXCLUDE_FUNCTIONS = ["hypot", "eval", "exec", "open", "input"]
_ALLOWED_FUNCTIONS = get_all_static_methods(
    Calculator, skip_list=["evaluate", "allowed_fns_in_evaluate", "help"]
)
_MATH_LIB_FUNCTIONS = [
    name
    for name in dir(math)
    if callable(getattr(math, name))
    and name not in _ALLOWED_FUNCTIONS + _EXCLUDE_FUNCTIONS
]
