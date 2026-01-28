#!/usr/bin/env bash
set -euo pipefail

print_banner() {
  cat <<'EOF'
 ███████████     ███████    █████ █████           █████    ████
░░███░░░░░███  ███░░░░░███ ░░███ ░░███           ░░███    ░░███
 ░███    ░███ ███     ░░███ ░░███ ███    ██████  ███████   ░███
 ░██████████ ░███      ░███  ░░█████    ███░░███░░░███░    ░███
 ░███░░░░░███░███      ░███   ███░███  ░███ ░░░   ░███     ░███
 ░███    ░███░░███     ███   ███ ░░███ ░███  ███  ░███ ███ ░███
 ███████████  ░░░███████░   █████ █████░░██████   ░░█████  █████
░░░░░░░░░░░     ░░░░░░░    ░░░░░ ░░░░░  ░░░░░░     ░░░░░  ░░░░░
EOF
}

show_help() {
  cat <<'EOF'
Usage: bin/setup.sh [--shell zsh|bash] [--no-prompt]

Runs onboarding steps:
  - Install Python deps via Poetry
  - Build the boxctl base image
  - Optionally enable shell completion
EOF
}

shell=""
no_prompt="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --shell)
      shell="${2:-}"
      shift 2
      ;;
    --no-prompt)
      no_prompt="true"
      shift
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      show_help
      exit 1
      ;;
  esac
done

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

print_banner

# Check for Poetry 2+
check_poetry() {
  if ! command -v poetry >/dev/null 2>&1; then
    echo "Poetry not found." >&2
    return 1
  fi

  # Get Poetry version (output: "Poetry (version X.Y.Z)")
  local version_output
  version_output=$(poetry --version 2>/dev/null)
  local major_version
  major_version=$(echo "$version_output" | sed -n 's/.*version \([0-9]*\).*/\1/p')

  if [[ -z "$major_version" ]]; then
    echo "Could not determine Poetry version." >&2
    return 1
  fi

  if [[ "$major_version" -lt 2 ]]; then
    echo "Poetry version $major_version.x found, but version 2+ is required." >&2
    return 1
  fi

  return 0
}

show_poetry_install_instructions() {
  echo "" >&2
  echo "To install Poetry 2+:" >&2
  if command -v pipx >/dev/null 2>&1; then
    echo "  pipx install poetry" >&2
    echo "" >&2
    echo "Or upgrade if already installed:" >&2
    echo "  pipx upgrade poetry" >&2
  else
    echo "  Option 1: Install pipx first, then use 'pipx install poetry'" >&2
    echo "  Option 2: https://python-poetry.org/docs/#installation" >&2
  fi
  echo "" >&2
}

if ! check_poetry; then
  show_poetry_install_instructions
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker first." >&2
  exit 1
fi

if [[ "$no_prompt" != "true" ]]; then
  echo "Setup options (y/n). Default is yes."
  read -r -p "Install Python deps with Poetry? [Y/n] " answer_poetry
  read -r -p "Build the boxctl base image? [Y/n] " answer_build
  if [[ -z "$shell" ]]; then
    read -r -p "Enable shell completion (zsh/bash/skip)? [skip] " answer_shell
    shell="${answer_shell:-}"
  fi
fi

do_poetry="true"
do_build="true"
if [[ "$no_prompt" != "true" ]]; then
  if [[ "${answer_poetry:-}" =~ ^[Nn]$ ]]; then
    do_poetry="false"
  fi
  if [[ "${answer_build:-}" =~ ^[Nn]$ ]]; then
    do_build="false"
  fi
fi

if [[ "$do_poetry" == "true" ]]; then
  echo "Installing Python dependencies..."
  poetry install
fi

if [[ "$do_build" == "true" ]]; then
  echo "Building base image..."
  docker build -f Dockerfile.base -t boxctl-base:latest .
fi

if [[ -n "$shell" && "$shell" != "skip" ]]; then
  case "$shell" in
    zsh)
      rc_file="$HOME/.zshrc"
      completion_line="source $root_dir/bin/completions/boxctl-completion.zsh"
      ;;
    bash)
      rc_file="$HOME/.bashrc"
      completion_line="source $root_dir/bin/completions/boxctl-completion.bash"
      ;;
    *)
      echo "Unsupported shell: $shell (expected zsh or bash)" >&2
      exit 1
      ;;
  esac

  rc_modified="false"

  if [[ -f "$rc_file" ]] && grep -Fqx "$completion_line" "$rc_file"; then
    echo "Shell completion already enabled in $rc_file"
  else
    echo "$completion_line" >> "$rc_file"
    echo "Added shell completion to $rc_file"
    rc_modified="true"
  fi

  # Add bin directory to PATH
  path_marker="# boxctl PATH"
  path_line="export PATH=\"$root_dir/bin:\$PATH\""
  if [[ -f "$rc_file" ]] && grep -Fq "boxctl PATH" "$rc_file"; then
    echo "PATH already set in $rc_file"
  else
    {
      echo ""
      echo "$path_marker"
      echo "$path_line"
    } >> "$rc_file"
    echo "Added boxctl bin to PATH in $rc_file"
    rc_modified="true"
  fi

  # Add abox alias
  alias_marker="# boxctl alias"
  alias_line='alias abox="boxctl"'
  if [[ -f "$rc_file" ]] && grep -Fqx "$alias_line" "$rc_file"; then
    echo "Alias already set in $rc_file"
  else
    {
      echo ""
      echo "$alias_marker"
      echo "$alias_line"
    } >> "$rc_file"
    echo "Added abox alias to $rc_file"
    rc_modified="true"
  fi

  # Hint to source the file if changes were made
  if [[ "$rc_modified" == "true" ]]; then
    echo ""
    echo "To use abox now, run:"
    echo "  source $rc_file"
  fi
fi

echo "Setup complete."
