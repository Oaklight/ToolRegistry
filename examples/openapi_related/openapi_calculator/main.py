from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="OpenAPI Calculator",
    description="Provides OpenAPI calculator service for addition, subtraction, multiplication, and division.",
    version="1.0.0",
)


@app.get("/add", summary="Addition")
def add(a: float, b: float):
    """
    Calculate a + b and return the result.

    Args:
        a (float): The first operand.
        b (float): The second operand.

    Returns:
        dict: A dictionary containing the key "result" with the sum of a and b.
    """
    return {"result": a + b}


@app.get("/subtract", summary="Subtraction")
def subtract(a: float, b: float):
    """
    Calculate a - b and return the result.

    Args:
        a (float): The first operand.
        b (float): The second operand.

    Returns:
        dict: A dictionary containing the key "result" with the difference of a and b.
    """
    return {"result": a - b}


@app.get("/multiply", summary="Multiplication")
def multiply(a: float, b: float):
    """
    Calculate a * b and return the result.

    Args:
        a (float): The first operand.
        b (float): The second operand.

    Returns:
        dict: A dictionary containing the key "result" with the product of a and b.
    """
    return {"result": a * b}


@app.get("/divide", summary="Division")
def divide(a: float, b: float):
    """
    Calculate a / b and return the result.

    Args:
        a (float): The numerator.
        b (float): The denominator.

    Returns:
        dict: A dictionary containing the key "result" with the quotient of a and b.

    Raises:
        HTTPException: If b is zero.
    """
    if b == 0:
        raise HTTPException(status_code=400, detail="Divisor cannot be zero")
    return {"result": a / b}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
