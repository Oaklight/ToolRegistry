# OpenAPI Integration Test Server

[中文版](README_zh)

This server is intended as a test server for developing and testing OpenAPI integrations. It provides basic arithmetic operations (addition, subtraction, multiplication, and division) through OpenAPI endpoints, serving as a sample implementation for development purposes.

## Running the Server

To run the server, execute:

    python main.py

The application will read the environment variable `PORT` to determine the port on which to run. If `PORT` is not set, the server will default to port `8000`.

## Installation

Install the required dependencies by running:

    pip install -r requirements.txt

## Accessing the Service

Once the server is running, you can access it via:

    http://localhost:8000

(Replace `8000` with the value of the `PORT` environment variable if it has been customized.)
