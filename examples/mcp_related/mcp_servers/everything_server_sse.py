import sqlite3
from typing import List, Set, Union
import asyncio
import random
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts import Prompt
from mcp.server.fastmcp.resources import TextResource, BinaryResource
from pydantic import Field
from pydantic import BaseModel
from enum import Enum
from starlette.applications import Starlette


class LoggingLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class EchoInput(BaseModel):
    message: str = Field(..., description="Message to echo")


class AddInput(BaseModel):
    a: float = Field(..., description="First number")
    b: float = Field(..., description="Second number")


class LongRunningInput(BaseModel):
    duration: float = Field(10, description="Duration in seconds")
    steps: int = Field(5, description="Number of steps")


class SampleLLMInput(BaseModel):
    prompt: str = Field(..., description="Prompt to send")
    max_tokens: int = Field(100, description="Max tokens to generate")


class MessageType(str, Enum):
    ERROR = "error"
    SUCCESS = "success"
    DEBUG = "debug"


class AnnotatedMessageInput(BaseModel):
    message_type: MessageType = Field(..., description="Type of message")
    include_image: bool = Field(False, description="Include example image")


mcp = FastMCP("Everything Server", sse_path="/sse", message_path="/mcp/messages/")


# Echo functionality
@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"


@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"


# SQLite functionality
@mcp.resource("schema://main")
def get_schema() -> str:
    """Provide the database schema as a resource"""
    conn = sqlite3.connect("database.db")
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall()
    return "\n".join(sql[0] for sql in schema if sql[0])


@mcp.tool()
def query_data(sql: str) -> str:
    """Execute SQL queries safely"""
    conn = sqlite3.connect("database.db")
    try:
        result = conn.execute(sql).fetchall()
        return "\n".join(str(row) for row in result)
    except Exception as e:
        return f"Error: {str(e)}"


# Additional common utilities
@mcp.tool()
def get_server_info() -> dict:
    """Get server information"""
    return {
        "name": "Everything Server",
        "version": "1.0.0",
        "features": ["echo", "sqlite", "utilities"],
    }


@mcp.prompt()
def welcome_prompt() -> str:
    """Welcome message prompt"""
    return "Welcome to the Everything Server! How can I help you today?"


# Comprehensive Server tools
@mcp.tool(name="echo", description="Echoes back the input")
async def echo(input: EchoInput):
    return {"content": f"Echo: {input.message}"}


@mcp.tool(name="add", description="Adds two numbers")
async def add(input: AddInput):
    return {"content": f"Sum: {input.a + input.b}"}


@mcp.tool(name="long_running", description="Long running operation with progress")
async def long_running(input: LongRunningInput, ctx: Context):
    step_duration = input.duration / input.steps
    for i in range(input.steps):
        await asyncio.sleep(step_duration)
        await ctx.progress.update(i + 1, input.steps)
    return {"content": f"Completed in {input.duration}s"}


@mcp.tool(name="sample_llm", description="Sample LLM interaction")
async def sample_llm(input: SampleLLMInput):
    return {"content": f"LLM response to '{input.prompt[:20]}...'"}


@mcp.tool(name="annotated_message", description="Demonstrates annotated messages")
async def annotated_message(input: AnnotatedMessageInput):
    content = []
    if input.message_type == MessageType.ERROR:
        content.append({"type": "text", "text": "Error occurred!", "priority": 1.0})
    elif input.message_type == MessageType.SUCCESS:
        content.append({"type": "text", "text": "Operation succeeded", "priority": 0.7})
    else:
        content.append({"type": "text", "text": "Debug information", "priority": 0.3})

    if input.include_image:
        content.append(
            {
                "type": "image",
                "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/C/HgAGgwJ/lK3Q6wAAAABJRU5ErkJggg==",
                "mime_type": "image/png",
                "priority": 0.5,
            }
        )

    return {"content": content}


# Create SSE endpoint
app = mcp.sse_app()
