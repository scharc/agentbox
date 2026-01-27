#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""
LiteLLM MCP Server - provides LLM completion tools via MCP.

This MCP server wraps the LiteLLM proxy to provide:
- Multi-provider LLM access with automatic fallback
- Model aliases (default, fast, code, reasoning)
- Transparent handling of rate limits and context window errors

Requires LiteLLM proxy to be running (start-litellm.py).
"""

from __future__ import annotations

import os
from typing import Optional

import httpx
from fastmcp import FastMCP

# LiteLLM proxy URL (running locally in container)
LITELLM_URL = os.getenv("LITELLM_URL", "http://127.0.0.1:4000")
LITELLM_TIMEOUT = float(os.getenv("LITELLM_TIMEOUT", "120"))

mcp = FastMCP(
    name="litellm",
    instructions=(
        "LiteLLM MCP - access multiple LLM providers with automatic fallback. "
        "Use model aliases like 'default', 'fast', 'code', or 'reasoning' to "
        "select appropriate models. The proxy handles rate limits and context "
        "window errors by falling back to alternative providers."
    ),
)


async def _check_proxy_available() -> bool:
    """Check if LiteLLM proxy is running."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LITELLM_URL}/health", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False


@mcp.tool()
async def complete(
    prompt: str,
    model: str = "default",
    max_tokens: int = 4096,
    temperature: float = 0.7,
    system_prompt: Optional[str] = None,
) -> dict:
    """Generate a completion using LiteLLM with automatic fallback.

    The LiteLLM proxy routes requests through configured providers with
    automatic fallback on rate limits, context window errors, or failures.

    Args:
        prompt: The user prompt to complete
        model: Model alias - 'default', 'fast', 'code', or 'reasoning'
               (or a specific model name like 'gpt-4o')
        max_tokens: Maximum tokens to generate (default: 4096)
        temperature: Sampling temperature 0-2 (default: 0.7)
        system_prompt: Optional system prompt to prepend

    Returns:
        dict with 'content', 'model' (actual model used), and 'usage' stats
    """
    if not await _check_proxy_available():
        return {
            "success": False,
            "error": "LiteLLM proxy not running. Enable it in ~/.config/boxctl/config.yml with litellm.enabled: true",
            "content": None,
        }

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=LITELLM_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

        return {
            "success": True,
            "model": data.get("model", model),
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "finish_reason": data["choices"][0].get("finish_reason"),
        }

    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            error_detail = e.response.text[:500]

        return {
            "success": False,
            "error": f"HTTP {e.response.status_code}: {error_detail}",
            "content": None,
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": f"Request timed out after {LITELLM_TIMEOUT}s",
            "content": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": None,
        }


@mcp.tool()
async def chat(
    messages: list,
    model: str = "default",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> dict:
    """Multi-turn chat completion using LiteLLM.

    Args:
        messages: List of message dicts with 'role' and 'content'
                  e.g., [{"role": "user", "content": "Hello"}]
        model: Model alias or specific model name
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature 0-2

    Returns:
        dict with 'content', 'model', and 'usage' stats
    """
    if not await _check_proxy_available():
        return {
            "success": False,
            "error": "LiteLLM proxy not running",
            "content": None,
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=LITELLM_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

        return {
            "success": True,
            "model": data.get("model", model),
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "finish_reason": data["choices"][0].get("finish_reason"),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "content": None,
        }


@mcp.tool()
async def list_models() -> dict:
    """List available model aliases and their providers.

    Returns:
        dict with 'models' list containing available model configurations
    """
    if not await _check_proxy_available():
        return {
            "success": False,
            "error": "LiteLLM proxy not running",
            "models": [],
        }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{LITELLM_URL}/v1/models",
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

        return {
            "success": True,
            "models": data.get("data", []),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "models": [],
        }


@mcp.tool()
async def get_status() -> dict:
    """Check LiteLLM proxy status and configuration.

    Returns:
        dict with proxy status, health info, and configuration summary
    """
    available = await _check_proxy_available()

    if not available:
        return {
            "success": False,
            "status": "unavailable",
            "message": "LiteLLM proxy is not running. Enable it in ~/.config/boxctl/config.yml",
        }

    try:
        async with httpx.AsyncClient() as client:
            # Get health info
            health_response = await client.get(f"{LITELLM_URL}/health", timeout=5.0)
            health = health_response.json() if health_response.status_code == 200 else {}

            # Get model list
            models_response = await client.get(f"{LITELLM_URL}/v1/models", timeout=5.0)
            models = models_response.json().get("data", []) if models_response.status_code == 200 else []

        return {
            "success": True,
            "status": "running",
            "url": LITELLM_URL,
            "health": health,
            "model_count": len(models),
            "models": [m.get("id") for m in models[:10]],  # First 10 models
        }

    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e),
        }


if __name__ == "__main__":
    mcp.run()
