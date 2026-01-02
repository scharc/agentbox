#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Generate/refold unified Agentbox config."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from agentbox.unified_config import (
    build_claude_config,
    build_codex_config,
    refold_unified_config,
    write_json,
    dump_toml,
    read_json,
    read_toml,
)


def _env_path(var_name: str, default: Path) -> Path:
    value = os.getenv(var_name)
    return Path(value) if value else default


def _paths() -> dict[str, Path]:
    return {
        "unified": _env_path(
            "AGENTBOX_UNIFIED_CONFIG",
            Path("/workspace/.agentbox/agentbox.config.json"),
        ),
        "claude_project": _env_path(
            "AGENTBOX_CLAUDE_PROJECT_CONFIG",
            Path("/workspace/.agentbox/config.json"),
        ),
        "codex_project": _env_path(
            "AGENTBOX_CODEX_PROJECT_CONFIG",
            Path("/workspace/.agentbox/codex.toml"),
        ),
    }


def generate() -> int:
    paths = _paths()
    unified = read_json(paths["unified"])
    if not unified:
        print("Error: unified config missing or invalid", file=sys.stderr)
        return 1

    claude_config = build_claude_config(unified, {})
    codex_config = build_codex_config(unified, {})

    write_json(paths["claude_project"], claude_config)
    paths["codex_project"].parent.mkdir(parents=True, exist_ok=True)
    paths["codex_project"].write_text(dump_toml(codex_config))
    return 0


def refold() -> int:
    paths = _paths()
    claude_config = read_json(paths["claude_project"])
    codex_config = read_toml(paths["codex_project"])
    if not claude_config and not codex_config:
        print("Error: per-agent configs missing", file=sys.stderr)
        return 1

    unified = refold_unified_config(
        claude_config,
        codex_config,
        {},
        {},
    )
    write_json(paths["unified"], unified)
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("generate", "refold"):
        print("Usage: unified-config.py [generate|refold]", file=sys.stderr)
        return 2
    if sys.argv[1] == "generate":
        return generate()
    return refold()


if __name__ == "__main__":
    raise SystemExit(main())
