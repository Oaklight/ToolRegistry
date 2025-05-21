# Best Practices for LLM Tools

## Key Principles

- **Stateless Functions:**  
  Functions should be stateless, relying only on the input parameters provided. This ensures predictable behavior.

  Stateless functions do not depend on any external state or previous interactions. This makes them easier to test, debug, and reuse across different contexts. By ensuring that each function call is independent, you can avoid unintended side effects and improve the reliability of your code.

- **Simple Input/Output Types with Type Hints:**  
  Use simple types for inputs and outputs, and include type hints to ensure clarity and type safety.

  Simple input and output types make functions easier to understand and use. Type hints provide additional context about what types of data are expected, which can help prevent errors and improve code readability. This is especially important in dynamically typed languages like Python, where type hints can serve as a form of documentation.

- **Docstrings:**  
  Always include docstrings to describe the function's purpose, parameters, and return values. This aids in understanding and usage.

  Docstrings are essential for documenting your code. They provide a clear explanation of what a function does, what inputs it expects, and what outputs it produces. This information is invaluable for other developers (or your future self) who may need to use or modify the function later.

- **Security Considerations:**  
  Validate inputs rigorously and implement access control to protect against exploitation.

  Security is a critical aspect of function design. Input validation helps prevent malicious data from causing harm, while access control ensures that only authorized users can execute certain functions. These measures are vital for protecting both the function itself and the systems it interacts with.

- **Testing Before Release:**  
  Conduct thorough testing to ensure function reliability and correctness.

  Testing is crucial for verifying that your functions work as intended. This includes unit tests to check individual components and integration tests to ensure that functions interact correctly with other parts of the system. Comprehensive testing helps catch bugs early and ensures a smooth deployment process.

## Example: Function Definition (Python)

```python
def calculate_area(length: float, width: float) -> float:
    """
    Calculate the area of a rectangle.

    Args:
        length (float): The length of the rectangle.
        width (float): The width of the rectangle.

    Returns:
        float: The area of the rectangle.
    """
    return length * width
```
