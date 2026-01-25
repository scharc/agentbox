# LiteLLM Integration Design

## Overview

Integrate LiteLLM into Agentbox to provide:
1. **Multi-provider LLM access** with automatic fallback (OpenAI, GWDG SAIA, Anthropic, etc.)
2. **MCP Gateway** for centralized tool management
3. **Cost tracking and rate limit handling** across providers

## Goals

1. Support multiple LLM providers with fallback chains
2. Add GWDG SAIA (OpenAI-compatible academic cloud) as a provider
3. Expose LiteLLM as both an API service and MCP server
4. System-wide configuration in `~/.config/agentbox/config.yml`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agentbox Container                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌─────────────────┐     ┌───────────────┐  │
│  │   Claude    │────▶│  LiteLLM Proxy  │────▶│   OpenAI API  │  │
│  │   Agent     │     │  (localhost)    │     └───────────────┘  │
│  └─────────────┘     │                 │                        │
│                      │  Fallback Chain │     ┌───────────────┐  │
│  ┌─────────────┐     │  1. OpenAI      │────▶│  GWDG SAIA    │  │
│  │   Codex     │────▶│  2. GWDG SAIA   │     │  (academic)   │  │
│  │   Agent     │     │  3. Anthropic   │     └───────────────┘  │
│  └─────────────┘     │                 │                        │
│                      └─────────────────┘     ┌───────────────┐  │
│  ┌─────────────┐            │               │  Anthropic    │  │
│  │  Analyst    │            │               └───────────────┘  │
│  │    MCP      │────────────┘                                   │
│  └─────────────┘                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Host Config (`~/.config/agentbox/config.yml`)

```yaml
litellm:
  enabled: true
  port: 4000                    # LiteLLM proxy port

  # Provider configurations
  providers:
    openai:
      api_key: ${OPENAI_API_KEY}

    gwdg_saia:
      api_base: https://chat-ai.academiccloud.de/v1
      api_key: ${GWDG_API_KEY}
      # Available models: llama-3.3-70b, qwen3-32b, deepseek-r1, mistral-large, codestral-22b

    anthropic:
      api_key: ${ANTHROPIC_API_KEY}

  # Model aliases with fallback chains
  models:
    # Default model - tries OpenAI first, falls back to GWDG
    default:
      - provider: openai
        model: gpt-4o
      - provider: gwdg_saia
        model: llama-3.3-70b

    # Fast model for quick tasks
    fast:
      - provider: openai
        model: gpt-4o-mini
      - provider: gwdg_saia
        model: llama-3.3-70b

    # Coding-focused model
    code:
      - provider: openai
        model: gpt-4o
      - provider: gwdg_saia
        model: codestral-22b

    # Reasoning model
    reasoning:
      - provider: gwdg_saia
        model: deepseek-r1
      - provider: openai
        model: o1

  # Fallback settings
  fallbacks:
    on_rate_limit: true         # Fallback on 429 errors
    on_context_window: true     # Fallback on context exceeded
    on_error: true              # Fallback on other errors

  # Router settings
  router:
    num_retries: 3
    timeout: 120
    retry_after_seconds: 60
```

### Environment Variables

```bash
# Required API keys (set in shell or .agentbox/.env)
OPENAI_API_KEY=sk-...
GWDG_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...

# Optional overrides
LITELLM_PORT=4000
LITELLM_LOG_LEVEL=INFO
```

## Implementation

### 1. Host Config Model (`agentbox/models/host_config.py`)

```python
class LiteLLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""
    api_key: Optional[str] = None  # Can use ${ENV_VAR} syntax
    api_base: Optional[str] = None

class LiteLLMModelDeployment(BaseModel):
    """A model deployment in a fallback chain."""
    provider: str
    model: str

class LiteLLMFallbackConfig(BaseModel):
    """Fallback behavior settings."""
    on_rate_limit: bool = True
    on_context_window: bool = True
    on_error: bool = True

class LiteLLMRouterConfig(BaseModel):
    """Router settings."""
    num_retries: int = 3
    timeout: int = 120
    retry_after_seconds: int = 60

class LiteLLMConfig(BaseModel):
    """LiteLLM configuration."""
    enabled: bool = False
    port: int = 4000
    providers: Dict[str, LiteLLMProviderConfig] = Field(default_factory=dict)
    models: Dict[str, List[LiteLLMModelDeployment]] = Field(default_factory=dict)
    fallbacks: LiteLLMFallbackConfig = Field(default_factory=LiteLLMFallbackConfig)
    router: LiteLLMRouterConfig = Field(default_factory=LiteLLMRouterConfig)
```

### 2. LiteLLM Service (`bin/start-litellm.py`)

Starts LiteLLM proxy inside the container:

```python
#!/usr/bin/env python3
"""Start LiteLLM proxy from host config."""

import os
import yaml
from pathlib import Path

def generate_litellm_config(host_config: dict) -> dict:
    """Convert agentbox config to LiteLLM config.yaml format."""
    litellm_cfg = host_config.get("litellm", {})

    model_list = []
    for alias, deployments in litellm_cfg.get("models", {}).items():
        for i, dep in enumerate(deployments):
            provider = dep["provider"]
            model = dep["model"]
            provider_cfg = litellm_cfg.get("providers", {}).get(provider, {})

            entry = {
                "model_name": alias,
                "litellm_params": {
                    "model": f"{provider}/{model}" if provider != "openai" else f"openai/{model}",
                }
            }

            # Add provider-specific settings
            if provider_cfg.get("api_base"):
                entry["litellm_params"]["api_base"] = provider_cfg["api_base"]
            if provider_cfg.get("api_key"):
                entry["litellm_params"]["api_key"] = provider_cfg["api_key"]

            # Add order for fallback priority
            entry["litellm_params"]["order"] = i + 1

            model_list.append(entry)

    return {
        "model_list": model_list,
        "router_settings": {
            "enable_pre_call_checks": True,
            **litellm_cfg.get("router", {})
        },
        "litellm_settings": {
            "num_retries": litellm_cfg.get("router", {}).get("num_retries", 3),
        }
    }

def main():
    # Load host config (mounted from host)
    config_path = Path("/host-config/agentbox/config.yml")
    if config_path.exists():
        with open(config_path) as f:
            host_config = yaml.safe_load(f) or {}
    else:
        host_config = {}

    litellm_cfg = host_config.get("litellm", {})
    if not litellm_cfg.get("enabled"):
        print("LiteLLM not enabled in config")
        return

    # Generate LiteLLM config
    config = generate_litellm_config(host_config)

    # Write config file
    config_file = Path("/tmp/litellm-config.yaml")
    with open(config_file, "w") as f:
        yaml.dump(config, f)

    # Start LiteLLM proxy
    port = litellm_cfg.get("port", 4000)
    os.execvp("litellm", [
        "litellm",
        "--config", str(config_file),
        "--port", str(port),
        "--host", "127.0.0.1",
    ])

if __name__ == "__main__":
    main()
```

### 3. LiteLLM MCP Server (`library/mcp/litellm/`)

Wraps LiteLLM as an MCP server for tool-based access:

```python
#!/usr/bin/env python3
"""LiteLLM MCP Server - provides LLM completion tools via MCP."""

from fastmcp import FastMCP
import httpx

mcp = FastMCP(
    name="litellm",
    instructions="LiteLLM MCP - access multiple LLM providers with automatic fallback."
)

LITELLM_URL = "http://127.0.0.1:4000"

@mcp.tool()
async def complete(
    prompt: str,
    model: str = "default",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> dict:
    """Generate a completion using LiteLLM with automatic fallback.

    Args:
        prompt: The prompt to complete
        model: Model alias (default, fast, code, reasoning)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0-2)

    Returns:
        Completion result with model used and content
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()

    return {
        "model": data["model"],
        "content": data["choices"][0]["message"]["content"],
        "usage": data.get("usage", {}),
    }

@mcp.tool()
async def list_models() -> dict:
    """List available model aliases and their providers."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{LITELLM_URL}/v1/models")
        response.raise_for_status()

    return response.json()

if __name__ == "__main__":
    mcp.run()
```

### 4. Container Init Integration

Add to `container-init.sh`:

```bash
# Start LiteLLM proxy if enabled
start_litellm() {
    local config_file="/host-config/agentbox/config.yml"
    if [[ ! -f "${config_file}" ]]; then
        return
    fi

    # Check if LiteLLM is enabled
    local enabled=$(python3 -c "
import yaml
with open('${config_file}') as f:
    cfg = yaml.safe_load(f) or {}
print(cfg.get('litellm', {}).get('enabled', False))
" 2>/dev/null)

    if [[ "${enabled}" == "True" ]]; then
        echo "Starting LiteLLM proxy..."
        su -s /bin/bash abox -c "nohup python3 /usr/local/bin/start-litellm.py >> /tmp/litellm.log 2>&1 &"
    fi
}

start_litellm
```

### 5. Dockerfile Addition

```dockerfile
# Install LiteLLM
RUN pip3 install --no-cache-dir --break-system-packages \
    litellm[proxy]
```

## GWDG SAIA Provider Details

From [GWDG SAIA Documentation](https://docs.hpc.gwdg.de/services/saia/index.html):

- **Base URL**: `https://chat-ai.academiccloud.de/v1`
- **Auth**: Bearer token via `Authorization` header
- **Compatible endpoints**: `/chat/completions`, `/completions`, `/embeddings`, `/models`

**Available Models**:
- Text: `llama-3.3-70b`, `qwen3-32b`, `mistral-large`, `codestral-22b`
- Reasoning: `deepseek-r1`, `qwq-32b`
- Vision: `qwen2.5-vl-72b`
- Embeddings: `e5-mistral-7b`, `multilingual-e5-large`

## Usage Examples

### Using LiteLLM API directly

```python
import openai

client = openai.OpenAI(
    base_url="http://127.0.0.1:4000/v1",
    api_key="not-needed",  # LiteLLM handles auth
)

response = client.chat.completions.create(
    model="default",  # Uses fallback chain
    messages=[{"role": "user", "content": "Hello!"}],
)
```

### Using LiteLLM MCP

```python
# Via analyst MCP or other agents
result = await litellm.complete(
    prompt="Explain this code",
    model="code",  # Uses code-focused fallback chain
)
```

### Environment setup

```bash
# In ~/.config/agentbox/.env or shell
export OPENAI_API_KEY="sk-..."
export GWDG_API_KEY="your-gwdg-token"
```

## Migration Path

1. **Phase 1**: Add LiteLLM config model and service startup
2. **Phase 2**: Create LiteLLM MCP server
3. **Phase 3**: Update analyst MCP to optionally use LiteLLM for API-based analysis
4. **Phase 4**: Add CLI commands (`agentbox litellm status`, `agentbox litellm models`)

## Security Considerations

1. API keys stored in environment variables (not config files)
2. LiteLLM binds to localhost only (127.0.0.1)
3. No external network access to LiteLLM proxy
4. Keys can reference `${ENV_VAR}` syntax in config

## Sources

- [LiteLLM MCP Overview](https://docs.litellm.ai/docs/mcp)
- [LiteLLM Fallback Configuration](https://docs.litellm.ai/docs/proxy/reliability)
- [LiteLLM Docker Setup](https://docs.litellm.ai/docs/proxy/deploy)
- [LiteLLM Multi-Provider Config](https://docs.litellm.ai/docs/proxy/configs)
- [GWDG SAIA Documentation](https://docs.hpc.gwdg.de/services/saia/index.html)
