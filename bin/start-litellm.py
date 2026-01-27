#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""
LiteLLM Proxy Startup Script

Reads LiteLLM configuration from the host config and starts the LiteLLM proxy.
The proxy provides:
- Multi-provider LLM access with automatic fallback
- OpenAI-compatible API on localhost
- Rate limit and context window error handling

Configuration is in ~/.config/boxctl/config.yml under the 'litellm' key.
"""

import os
import re
import sys
from pathlib import Path

import yaml


def resolve_env_vars(value: str) -> str:
    """Resolve ${ENV_VAR} syntax in config values."""
    if not isinstance(value, str):
        return value

    def replace_env(match):
        var_name = match.group(1)
        return os.getenv(var_name, "")

    return re.sub(r"\$\{(\w+)\}", replace_env, value)


def generate_litellm_config(host_config: dict) -> dict:
    """Convert boxctl config to LiteLLM config.yaml format.

    Args:
        host_config: The host configuration dict from config.yml

    Returns:
        LiteLLM-compatible configuration dict
    """
    litellm_cfg = host_config.get("litellm", {})
    providers = litellm_cfg.get("providers", {})
    models = litellm_cfg.get("models", {})
    router_cfg = litellm_cfg.get("router", {})
    fallbacks_cfg = litellm_cfg.get("fallbacks", {})

    model_list = []
    fallbacks = []
    context_window_fallbacks = []

    for alias, deployments in models.items():
        if not deployments:
            continue

        # Build fallback chain for this alias
        fallback_chain = []

        for i, dep in enumerate(deployments):
            provider = dep.get("provider", "openai")
            model = dep.get("model", "gpt-4o")
            provider_cfg = providers.get(provider, {})

            # Determine the model prefix based on provider
            # LiteLLM uses provider prefixes like openai/, anthropic/, etc.
            if provider == "openai":
                litellm_model = f"openai/{model}"
            elif provider == "anthropic":
                litellm_model = f"anthropic/{model}"
            else:
                # Generic OpenAI-compatible provider
                litellm_model = f"openai/{model}"

            entry = {
                "model_name": alias,
                "litellm_params": {
                    "model": litellm_model,
                },
            }

            # Add provider-specific settings
            api_base = provider_cfg.get("api_base")
            if api_base:
                entry["litellm_params"]["api_base"] = resolve_env_vars(api_base)

            api_key = provider_cfg.get("api_key")
            if api_key:
                entry["litellm_params"]["api_key"] = resolve_env_vars(api_key)

            # Add order for fallback priority (lower = higher priority)
            entry["litellm_params"]["order"] = i + 1

            model_list.append(entry)

            # Track for fallback chain
            if i > 0:
                fallback_chain.append(alias)

        # Build fallback mappings
        if len(deployments) > 1:
            # For multi-deployment aliases, each entry falls back to the next
            fallbacks.append({alias: [alias]})  # LiteLLM handles order via 'order' param

    # Build the final config
    config = {
        "model_list": model_list,
        "router_settings": {
            "enable_pre_call_checks": fallbacks_cfg.get("on_context_window", True),
            "num_retries": router_cfg.get("num_retries", 3),
            "timeout": router_cfg.get("timeout", 120),
            "retry_after": router_cfg.get("retry_after_seconds", 60),
        },
        "litellm_settings": {
            "num_retries": router_cfg.get("num_retries", 3),
            "request_timeout": router_cfg.get("timeout", 120),
        },
    }

    return config


def main():
    # Look for host config in multiple locations
    config_paths = [
        Path("/host-config/boxctl/config.yml"),  # Mounted from host
        Path.home() / ".config" / "boxctl" / "config.yml",  # Direct path
        Path("/workspace/.boxctl/host-config.yml"),  # Alternative location
    ]

    host_config = {}
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    host_config = yaml.safe_load(f) or {}
                print(f"Loaded config from {config_path}")
                break
            except Exception as e:
                print(f"Warning: Failed to load {config_path}: {e}")

    litellm_cfg = host_config.get("litellm", {})

    if not litellm_cfg.get("enabled"):
        print("LiteLLM not enabled in config (litellm.enabled: false)")
        print("Enable it in ~/.config/boxctl/config.yml:")
        print("  litellm:")
        print("    enabled: true")
        sys.exit(0)

    # Check if we have any models configured
    if not litellm_cfg.get("models"):
        print("No models configured for LiteLLM")
        print("Add models in ~/.config/boxctl/config.yml:")
        print("  litellm:")
        print("    models:")
        print("      default:")
        print("        - provider: openai")
        print("          model: gpt-4o")
        sys.exit(1)

    # Generate LiteLLM config
    config = generate_litellm_config(host_config)

    if not config.get("model_list"):
        print("No valid model configurations generated")
        sys.exit(1)

    # Write config file
    config_file = Path("/tmp/litellm-config.yaml")
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"Generated LiteLLM config at {config_file}")
    print(f"Models configured: {len(config['model_list'])}")

    # Start LiteLLM proxy
    port = litellm_cfg.get("port", 4000)
    print(f"Starting LiteLLM proxy on port {port}...")

    # Use exec to replace this process with litellm
    os.execvp(
        "litellm",
        [
            "litellm",
            "--config",
            str(config_file),
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
        ],
    )


if __name__ == "__main__":
    main()
