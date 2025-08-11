# Calculator - Mathematical calculation tools

```{note}
Refactored in version: 0.4.12 <br>
Refined in version: 0.4.8.post1 <br>
Refined in version: 0.4.3 <br>
New in version: 0.4.2
```

The Calculator is designed to be safe and easy for LLM agents to use. It supports expression evaluation and provides utility functions for interacting with mathematical operations.

## Calculator

The Calculator exposes three main functions:

- `help`: Displays the signature and docstring of a function.
- `list_allowed_fns`: Lists permitted functions and constants from `BaseCalculator` and Python's `math` library. `with_help` parameter can be used to include function signatures and docstrings. Returns a json string.
- `evaluate`: Evaluates expressions using functions from Calculator and Python's math library.

The Calculator is recommended for most users due to its simplicity and comprehensive functionality.

### Note on Arithmetic Operations

Basic arithmetic operations such as `+`, `-`, `*`, `/`, `//`, and `%` can be expressed either through native Python operators or their corresponding named functions. When using named functions like `add`, `subtract`, `multiply`, `divide`, `floor_divide`, or `mod`, be mindful of operator precedence to ensure accurate calculations. For example:

```python
from toolregistry.hub import Calculator as calc
print(calc.evaluate("add(2, 3) * pow(2, 3) + sqrt(16)"))  # Output: 44
print(calc.evaluate("(2 + 3) * (2 ** 3) + sqrt(16)"))  # Output: 44
```

`evaluate` already includes related docstring for "operator precedence", so LLM should be able to understand it.

## BaseCalculator

The BaseCalculator provides the core mathematical operations, which are utilized internally by the Calculator. It is suitable for advanced users who need direct access to individual mathematical functions.

- Basic arithmetic: add, subtract, multiply, divide, floor_divide, mod
- Numerical processing: abs, round
- Power and roots: pow, sqrt, cbrt
- Logarithmic and exponential functions: log, ln, exp
- Statistical functions: min, max, sum, average, median, mode, standard_deviation
- Combinatorics: factorial, gcd, lcm, comb, perm
- Distance and norm: dist, dist_manhattan, norm_euclidean
- Financial calculations: simple_interest, compound_interest

Example usage:

```python
from toolregistry.hub import BaseCalculator as base_calc
print(base_calc.add(1, 2))  # Output: 3
```

For most users, the Calculator is the preferred choice due to its ease of use and additional features.
