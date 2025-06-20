import inspect
import json
import math
import textwrap
from typing import Dict, List, Literal, Union

from ..native.utils import get_all_static_methods


class BaseCalculator:
    """Base class for Calculator, providing core mathematical operations."""

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
    def floor_divide(a: float, b: float) -> float:
        """Floor divides a by b. b != 0"""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a // b

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
        mean = BaseCalculator.average(numbers)
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

    @staticmethod
    def hypot(*args: float) -> float:
        """Calculates Euclidean norm (hypotenuse) of input values."""
        return math.hypot(*args)

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
            evaluate, list_allowed_fns, help
    """

    # ====== Expression evaluation 表达式求值 ======

    @staticmethod
    def _allowed_functions() -> List[str]:
        return _ALLOWED_FUNCTIONS + _MATH_LIB_FUNCTIONS

    @staticmethod
    def list_allowed_fns(with_help: bool = False) -> str:
        """Returns a JSON string of allowed functions for the evaluate method with their descriptions.

        Each key is the name of an allowed function, and the value is its help message.
        This allows quick access to both the list of functions and their descriptions without needing multiple queries.

        Args:
            with_help (bool, optional): If True, includes descriptions of each function. Defaults to False.

        Returns:
            str: A JSON string containing the allowed functions, if with_help is True, their descriptions.
        """
        allowed_functions = Calculator._allowed_functions()

        if not with_help:
            return json.dumps(allowed_functions)

        function_help = {}

        for fn_name in allowed_functions:
            function_help[fn_name] = Calculator.help(fn_name)

        return json.dumps(function_help)

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
        if fn_name not in Calculator._allowed_functions() + [
            "evaluate",
            "list_allowed_fns",
        ]:
            raise ValueError(f"Function '{fn_name}' is not recognized.")

        # Resolving whether the function is from Calculator or math
        if hasattr(BaseCalculator, fn_name):
            target = getattr(BaseCalculator, fn_name)
        elif hasattr(math, fn_name):  # Handle math functions
            target = getattr(math, fn_name)
        else:
            target = None

        if target is None:
            raise ValueError(f"Function '{fn_name}' cannot be resolved.")

        # If the attribute is not callable (i.e., constant), skip signature retrieval
        if callable(target):
            docstring = inspect.getdoc(target) or ""
            docstring = docstring.strip()
            signature = inspect.signature(target)
            return (
                f"function: {fn_name}{signature}\n{textwrap.indent(docstring, ' ' * 4)}"
            )
        else:
            docstring = f"Constant value: {target!r}"
            return f"constant: {fn_name}\n{textwrap.indent(docstring, ' ' * 4)}"

    @staticmethod
    def evaluate(expression: str) -> Union[float, int, bool]:
        """Evaluates a mathematical expression.

        The `expression` can use named functions like `add(2, 3)` or native operators like `2 + 3`. Pay attention to operator precedence and use parentheses to ensure the intended order of operations. For example: `"add(2, 3) * pow(2, 3) + sqrt(16)"` or `"(2 + 3) * (2 ** 3) + sqrt(16)"` or mixed.

        - Use `list_allowed_fns()` to view available functions. Set `with_help` to `True` to include function signatures and docstrings.
        - Use `help` for detailed information on specific functions.

        **Note**: If an error occurs due to an invalid expression, query the `help` method to check the function usage and ensure it is listed by `list_allowed_fns()`.

        Args:
            expression (str): Mathematical expression to evaluate.

        Returns:
            Union[float, int, bool]: Result of the evaluation.

        Raises:
            ValueError: If the expression is invalid or evaluation fails.
        """
        # Get all static methods from Calculator class using __dict__,
        # excluding 'evaluate' to avoid redundancy.
        allowed_functions = {}

        allowed_functions.update(
            {name: getattr(math, name) for name in _MATH_LIB_FUNCTIONS}
        )

        allowed_functions.update(
            {
                name: func.__func__
                for name, func in BaseCalculator.__dict__.items()
                if isinstance(func, staticmethod) and name in _ALLOWED_FUNCTIONS
            }
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
_ALLOWED_FUNCTIONS = get_all_static_methods(BaseCalculator)
_EXCLUDE_FUNCTIONS = ["hypot", "eval", "exec", "open", "input"]
_MATH_LIB_FUNCTIONS = [
    name
    for name in dir(math)
    if (
        callable(getattr(math, name)) or isinstance(getattr(math, name), float)
    )  # include constants
    and name not in _ALLOWED_FUNCTIONS + _EXCLUDE_FUNCTIONS
]
