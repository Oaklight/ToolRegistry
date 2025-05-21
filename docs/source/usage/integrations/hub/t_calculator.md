# Calculator - Mathematical calculation tools

```{tip}
Refined in version: 0.4.8.post1
Refined in version: 0.4.3
New in version: 0.4.2
```

It's designed to be safe and easy for llm agents to use. It supports both individual function calls and expression evaluation.

It also includes a help function that displays the signature and docstring of a function.

The Calculator provides a comprehensive set of mathematical functions:

- Basic arithmetic: add, subtract, multiply, divide, mod
- Numerical processing: abs, round
- Power and roots: pow, sqrt, cbrt
- Logarithmic and exponential functions: log, ln, exp
- Statistical functions: min, max, sum, average, median, mode, standard_deviation
- Combinatorics: factorial, gcd, lcm, comb, perm
- Distance and norm: dist, dist_manhattan, norm_euclidean
- Financial calculations: simple_interest, compound_interest
- Expression evaluation: evaluate, allowed_fns_in_evaluate, help
  - `evaluate` evaluates expressions using functions from Calculator and Python's math library.
  - `allowed_fns_in_evaluate` lists permitted functions.
  - `help` displays the signature and docstring of a function.

Example usage:

```python
from toolregistry.hub import Calculator as calc
print(calc.add(1, 2))  # Output: 3
print(calc.evaluate("add(2, 3) * pow(2, 3) + sqrt(16)"))  # Output: 44
```
