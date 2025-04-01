# Best Practices for Writing LLM Function Tools

## 1. Design Principles

- **Atomicity:**  
  Each function should address a single, well-defined task. For instance, use `get_weather` instead of a broader `weather_assistant` function. This promotes modularity and easier LLM composition.
- **Clarity of Input/Output:**  
  Define parameter types precisely (e.g., `location: string, format: "city name"`). Use JSON Schema for structured, predictable return values. Avoid ambiguous or overly generic types.
- **Stateless Functions:**  
  Functions should be stateless. Each invocation should be self-contained, relying only on the input parameters provided in that specific call. This ensures predictable and repeatable behavior.

## 2. Security & Robustness

- **Strict Input Validation:**  
  Validate all inputs rigorously. Check formats (e.g., dates: `YYYY-MM-DD`), ranges, and required fields. Provide informative error messages (e.g., `{"error": "invalid_date_format", "detail": "'start_date' must be YYYY-MM-DD"}`).
- **Sandboxed Execution Environment:**  
  Execute potentially risky operations (like database queries or external API calls) within isolated environments. Implement timeouts and resource limits to prevent abuse or runaway processes.
- **Access Control & Permissions:**  
  Implement authorization based on user roles or API keys. Limit function access and usage (e.g., API rate limits, feature gating) as needed. Document required permissions clearly in function descriptions.

## 3. Documentation & Metadata

- **Comprehensive Natural Language Descriptions:**  
  Provide detailed, natural language descriptions for each function and its parameters. Example: `"currency_code: ISO 4217 currency code (e.g., USD, EUR, CNY)"`. Focus on _what_ the function does and _how_ to use parameters.
- **Illustrative Example Annotations:**  
  Incorporate clear, concise input/output examples, ideally in OpenAPI format or similar. These examples significantly aid LLMs in understanding function usage and expected data structures.
- **Function Versioning:**  
  Use versioning (e.g., `get_weather_v1`, `get_weather_v2`) to manage API changes and maintain backward compatibility. This allows for updates without breaking existing LLM integrations.

## 4. Error Handling Strategy

- **Structured, Machine-Readable Error Codes:**  
  Return errors in a structured format that LLMs can parse and react to programmatically. Use consistent error codes and include detailed error messages.

  ```json
  {
    "error": "authentication_failed",
    "code": "AUTH_001",
    "detail": "Invalid API key provided."
  }
  ```

- **Documented Retry Policies:**  
  For transient errors (e.g., network hiccups, temporary service unavailability), document whether and how the LLM should retry function calls. Specify retry intervals, maximum attempts, etc.
- **Fallback & Degraded Service Modes:**  
  For critical functions, provide fallback mechanisms. This could involve returning cached data, using a simplified algorithm, or offering a reduced functionality version in case of primary service failure.

## 5. Performance Optimization Techniques

- **Strategic Caching:**  
  Cache frequently accessed, relatively static data (e.g., exchange rates, geographic data) with appropriate Time-To-Live (TTL) settings. Include `cache_ttl` in function metadata where relevant.
- **Batch Processing Capabilities:**  
  Design functions to accept arrays or lists as input (e.g., `user_ids: string[]`). This enables batch operations, reducing the overhead of multiple individual function calls.
- **Lazy Initialization of Resources:**  
  Defer initialization of resource-intensive components (e.g., large language models, database connections, complex libraries) until they are actually needed. This minimizes startup latency and resource consumption.

## 6. LLM-Centric Design Considerations

- **Parameter Synonyms & Aliases:**  
  Anticipate common variations in user input. Map synonyms and aliases to standardized parameter names. For example, accept both "phone" and "mobile" and internally map them to a `phone_number` parameter.
- **Multimodal Input/Output Support:**  
  If the LLM is multimodal, design functions that can handle diverse input types (images, audio, video) and produce multimodal outputs. For example, a function to analyze an image or generate a caption.
- **Contextual Awareness Enhancement:**  
  Allow functions to optionally receive conversational context (e.g., `conversation_history`, `user_intent`). This context can enable more intelligent function behavior and improve relevance.

## 7. Testing & Validation Procedures

- **Comprehensive Unit Test Suite:**  
  Develop unit tests that cover normal use cases, edge cases (empty inputs, very long strings, invalid formats), and error conditions. Mock LLM inputs to simulate various scenarios.
- **End-to-End Integration Tests:**  
  Embed functions in realistic conversational flows and test the complete interaction with the LLM. Verify that the LLM correctly chooses and invokes functions in different dialog contexts.
- **Continuous Monitoring & Logging:**  
  Implement robust monitoring to track function call frequency, latency, error rates, and resource usage. Log detailed function execution information for debugging and performance analysis. Use metrics to drive iterative improvements.

## Example: Improved Function Definition (Python)

```python
import datetime

def get_stock_price(
    symbol: str,       # Stock ticker symbol (e.g., AAPL, GOOG)
    exchange: str = "NASDAQ",  # Exchange code (default: NASDAQ)
    currency: str = "USD"      # Currency for price (default: USD)
) -> dict:
    """
    Fetches the current, delayed (15-minute) stock price for a given symbol.

    Args:
        symbol (str):  Required. The stock ticker symbol. Must be a valid symbol listed on the specified exchange.
        exchange (str, optional): The exchange code (e.g., NASDAQ, NYSE). Defaults to "NASDAQ".
        currency (str, optional): The currency in which to return the price (e.g., USD, EUR, CNY). Defaults to "USD".

    Returns:
        dict: A dictionary containing the stock price, currency, and timestamp.
              Example: {"price": 168.32, "currency": "USD", "timestamp": "2025-02-23T14:30:00Z"}

    Raises:
        ValueError: If the stock symbol is invalid, the currency is not supported, or input validation fails.
        TimeoutError: If there is a timeout fetching data from the external data source.
        LookupError: If the stock symbol is not found on the specified exchange.

    Example:
        >>> get_stock_price("AAPL", currency="CNY")
        {'price': 168.32, 'currency': 'CNY', 'timestamp': '2025-02-23T14:30:00Z'}

    Error Example:
        >>> get_stock_price("INVALID_SYMBOL")
        ValueError: Invalid stock symbol: INVALID_SYMBOL
    """
    # --- Input Validation ---
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("Invalid symbol: Symbol must be a non-empty string.")
    allowed_currencies = ["USD", "EUR", "CNY", "GBP"] # Example allowed currencies
    if currency.upper() not in allowed_currencies:
        raise ValueError(f"Unsupported currency: {currency}. Allowed currencies: {', '.join(allowed_currencies)}")

    # --- [Placeholder] External API Call (Replace with actual API interaction) ---
    try:
        # Simulate API call and data retrieval (replace with actual API call)
        if symbol.upper() == "INVALID_SYMBOL": # Simulate invalid symbol
            raise LookupError("Stock symbol not found.")
        price_data = {
            "AAPL": {"USD": 170.50, "CNY": 1234.56},
            "GOOG": {"USD": 2700.10, "EUR": 2500.00}
        } # Example data (replace with actual API response parsing)

        if symbol.upper() not in price_data:
            raise LookupError(f"Stock symbol '{symbol}' not found.")
        if currency.upper() not in price_data[symbol.upper()]:
             raise ValueError(f"Price in currency '{currency}' not available for symbol '{symbol}'.")

        price = price_data[symbol.upper()][currency.upper()]
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return {
            "price": price,
            "currency": currency.upper(),
            "timestamp": timestamp
        }

    except LookupError as e:
        raise LookupError(f"Stock symbol not found: {symbol}") from e # Re-raise with more context
    except TimeoutError as e:
        raise TimeoutError("Timeout fetching stock data from external source.") from e # Re-raise

    except Exception as e: # Catch-all for other potential errors (API issues, etc.)
        raise RuntimeError(f"Error fetching stock price: {e}") from e # Raise a more general error
```

## Implementation Notes

- Prioritize functions that demonstrably reduce LLM hallucinations and enhance factual accuracy (e.g., reliable calculators, up-to-date information retrieval).
