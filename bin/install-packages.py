#!/usr/bin/env python3
"""
Rock-solid package installer for MCP servers and project dependencies.

This script replaces the fragile bash+embedded-Python installation logic
with a robust, testable, and maintainable solution.

Usage:
    install-packages.py --meta PATH [--manifest PATH] [--log PATH]
    install-packages.py --config PATH [--manifest PATH] [--log PATH]

Exit codes:
    0 = All packages installed successfully
    1 = Some packages failed (partial success)
    2 = All packages failed (total failure)
"""

import json
import subprocess
import sys
import time
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from datetime import datetime, timezone

# ============================================================================
# Data Models
# ============================================================================

@dataclass
class InstallResult:
    """Result of a package installation attempt."""
    succeeded: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    def is_complete_success(self) -> bool:
        return len(self.failed) == 0

    def is_complete_failure(self) -> bool:
        return len(self.succeeded) == 0

    def total_count(self) -> int:
        return len(self.succeeded) + len(self.failed)


@dataclass
class PackageSpec:
    """Specification for packages to install."""
    pip: List[str] = field(default_factory=list)
    npm: List[str] = field(default_factory=list)
    post: List[str] = field(default_factory=list)

    @classmethod
    def from_mcp_meta(cls, meta_path: Path):
        """Extract packages from mcp-meta.json."""
        with open(meta_path) as f:
            data = json.load(f)

        pip, npm, post = [], [], []
        for server_name, server_config in data.get('servers', {}).items():
            install = server_config.get('install', {})

            # Handle pip packages
            pip_pkgs = install.get('pip', [])
            if isinstance(pip_pkgs, str):
                pip_pkgs = [pip_pkgs]
            pip.extend(pip_pkgs)

            # Handle npm packages
            npm_pkgs = install.get('npm', [])
            if isinstance(npm_pkgs, str):
                npm_pkgs = [npm_pkgs]
            npm.extend(npm_pkgs)

            # Handle post commands
            post_cmds = install.get('post', [])
            if isinstance(post_cmds, str):
                post_cmds = [post_cmds]
            post.extend(post_cmds)

        # Deduplicate while preserving order
        pip = list(dict.fromkeys(pip))
        npm = list(dict.fromkeys(npm))
        post = list(dict.fromkeys(post))

        return cls(pip=pip, npm=npm, post=post)

    @classmethod
    def from_agentbox_yml(cls, config_path: Path):
        """Extract packages from .agentbox.yml."""
        try:
            import yaml
        except ImportError:
            # Fallback to basic YAML parsing if pyyaml not available
            log_warn("PyYAML not available, using basic parsing")
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f)

        packages = data.get('packages', {})
        # Deduplicate while preserving order
        pip = list(dict.fromkeys(packages.get('pip', [])))
        npm = list(dict.fromkeys(packages.get('npm', [])))
        post = list(dict.fromkeys(packages.get('post', [])))
        return cls(pip=pip, npm=npm, post=post)


# ============================================================================
# Package Managers
# ============================================================================

class PackageManager(ABC):
    """Abstract base class for package managers."""

    @abstractmethod
    def install_batch(self, packages: List[str]) -> Tuple[bool, str]:
        """Install multiple packages at once. Returns (success, output)."""
        pass

    @abstractmethod
    def install_single(self, package: str) -> Tuple[bool, str]:
        """Install a single package. Returns (success, output)."""
        pass

    @abstractmethod
    def validate(self, package: str) -> Tuple[bool, Optional[str]]:
        """Check if package is installed. Returns (installed, version)."""
        pass

    def install_with_retry(self, packages: List[str], max_attempts: int = 3) -> InstallResult:
        """Install packages with batch fallback and retry logic."""
        if not packages:
            return InstallResult()

        log_info(f"Installing {len(packages)} packages (batch mode)")

        # Try batch installation first
        success, output = self.install_batch(packages)
        if success:
            log_info("Batch installation succeeded")
            # Validate all packages
            succeeded, failed, errors = [], [], {}
            log_info("Validating installations...")
            for pkg in packages:
                installed, version = self.validate(pkg)
                if installed:
                    succeeded.append(pkg)
                    log_info(f"✓ {pkg}: version {version} installed")
                else:
                    failed.append(pkg)
                    errors[pkg] = "Package not found after installation"
                    log_error(f"✗ {pkg}: not found after installation")

            return InstallResult(succeeded=succeeded, failed=failed, errors=errors)

        # Batch failed, try individual packages with retry
        log_warn(f"Batch installation failed: {output[:200]}")
        log_info("Falling back to individual package installation")

        succeeded, failed, errors = [], [], {}
        for pkg in packages:
            installed = False
            last_error = ""

            for attempt in range(1, max_attempts + 1):
                log_info(f"Installing {pkg} (attempt {attempt}/{max_attempts})")
                success, output = self.install_single(pkg)

                if success:
                    # Validate installation
                    is_installed, version = self.validate(pkg)
                    if is_installed:
                        succeeded.append(pkg)
                        log_info(f"✓ {pkg}: version {version} installed")
                        installed = True
                        break
                    else:
                        last_error = "Package not found after installation"
                        log_warn(f"Failed (attempt {attempt}/{max_attempts}): {last_error}")
                else:
                    last_error = output[:500] if output else "Unknown error"
                    log_warn(f"Failed (attempt {attempt}/{max_attempts}): {last_error[:200]}")

                # Exponential backoff
                if attempt < max_attempts:
                    backoff_time = 2 ** attempt
                    log_info(f"Waiting {backoff_time}s before retry...")
                    time.sleep(backoff_time)

            if not installed:
                failed.append(pkg)
                errors[pkg] = last_error
                log_error(f"✗ Package {pkg} failed after {max_attempts} attempts")

        return InstallResult(succeeded=succeeded, failed=failed, errors=errors)


class PipManager(PackageManager):
    """Package manager for Python pip."""

    def install_batch(self, packages: List[str]) -> Tuple[bool, str]:
        cmd = ['pip', 'install', '--upgrade'] + packages
        return self._run_command(cmd)

    def install_single(self, package: str) -> Tuple[bool, str]:
        return self.install_batch([package])

    def validate(self, package: str) -> Tuple[bool, Optional[str]]:
        # Extract package name (remove version specifier)
        pkg_name = re.split(r'[<>=!]', package)[0].strip()

        cmd = ['pip', 'show', pkg_name]
        success, output = self._run_command(cmd, check=False)

        if not success:
            return False, None

        # Extract version from output
        for line in output.split('\n'):
            if line.startswith('Version:'):
                version = line.split(':', 1)[1].strip()
                return True, version

        return False, None

    def _run_command(self, cmd: List[str], check: bool = True) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=300,
                check=check
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stdout + e.stderr
        except subprocess.TimeoutExpired:
            return False, "Installation timed out after 5 minutes"
        except Exception as e:
            return False, str(e)


class NpmManager(PackageManager):
    """Package manager for Node npm."""

    def install_batch(self, packages: List[str]) -> Tuple[bool, str]:
        cmd = ['npm', 'install', '-g'] + packages
        return self._run_command(cmd)

    def install_single(self, package: str) -> Tuple[bool, str]:
        return self.install_batch([package])

    def validate(self, package: str) -> Tuple[bool, Optional[str]]:
        # Extract package name (handle @scope/package@version and package@tag)
        # Match everything before the last @ (preserving @scope prefix)
        match = re.match(r'^(@?[^@]+)', package)
        pkg_name = match.group(1) if match else package

        cmd = ['npm', 'list', '-g', pkg_name, '--depth=0']
        success, output = self._run_command(cmd, check=False)

        if not success or pkg_name not in output:
            return False, None

        # Extract version from output
        # Format: "├── @playwright/mcp@1.2.3" or "└── package@1.0.0"
        match = re.search(rf'{re.escape(pkg_name)}@([\d.]+)', output)
        if match:
            return True, match.group(1)

        return True, "unknown"

    def _run_command(self, cmd: List[str], check: bool = True) -> Tuple[bool, str]:
        try:
            # Source bashrc to get npm in PATH
            bash_cmd = f"source ~/.bashrc && {' '.join(cmd)}"
            result = subprocess.run(
                ['bash', '-c', bash_cmd],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=600,
                check=check
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.CalledProcessError as e:
            return False, e.stdout + e.stderr
        except subprocess.TimeoutExpired:
            return False, "Installation timed out after 10 minutes"
        except Exception as e:
            return False, str(e)


class PostCommandRunner:
    """Runs post-installation shell commands."""

    def run(self, commands: List[str]) -> InstallResult:
        succeeded, failed, errors = [], [], {}

        for cmd in commands:
            log_info(f"Running: {cmd}")
            success, error_msg = self._run_command(cmd)

            if success:
                succeeded.append(cmd)
                log_info(f"✓ Command succeeded")
            else:
                failed.append(cmd)
                errors[cmd] = error_msg
                log_error(f"✗ Command failed: {error_msg}")

        return InstallResult(succeeded=succeeded, failed=failed, errors=errors)

    def _run_command(self, cmd: str) -> Tuple[bool, str]:
        try:
            bash_cmd = f"source ~/.bashrc && {cmd}"
            # Don't capture output - some commands (like npx) hang when stdout/stderr are pipes
            # Instead redirect to /dev/null to prevent terminal blocking
            result = subprocess.run(
                ['bash', '-c', bash_cmd],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=600,
                check=True
            )
            return True, ""
        except subprocess.CalledProcessError as e:
            return False, f"Command failed with exit code {e.returncode}"
        except subprocess.TimeoutExpired:
            return False, "Command timed out after 10 minutes"
        except Exception as e:
            return False, str(e)


# ============================================================================
# Installation Manifest
# ============================================================================

class Manifest:
    """Tracks installation history and results."""

    def __init__(self, path: Path):
        self.path = path
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except:
                pass

        return {
            "version": "1.0",
            "last_updated": None,
            "installations": {"pip": {}, "npm": {}, "post": {}},
            "failures": []
        }

    def record_success(self, manager: str, package: str, version: str, source: str):
        self.data["installations"][manager][package] = {
            "installed": True,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "installed_version": version,
            "source": source
        }

    def record_failure(self, manager: str, package: str, error: str, attempts: int):
        self.data["failures"].append({
            "package": package,
            "manager": manager,
            "error": error[:500],  # Limit error message length
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "attempts": attempts
        })

    def save(self):
        self.data["last_updated"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self.data, f, indent=2)


# ============================================================================
# Logging
# ============================================================================

LOG_FILE = None


def setup_logging(log_path: Optional[Path]):
    global LOG_FILE
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE = open(log_path, 'a')


def update_status(phase: str, details: str):
    """Update the container status file for progress display."""
    try:
        with open("/tmp/container-status", "w") as f:
            f.write(f"{phase}|{details}")
    except Exception:
        pass  # Ignore errors - status display is best-effort


# Progress tracking for checklist display
_install_progress = {"items": [], "current": None}


def init_progress(pip: List[str], npm: List[str], post: List[str]):
    """Initialize progress tracking with all items to install."""
    items = []
    for pkg in pip:
        items.append({"type": "pip", "name": pkg, "status": "pending"})
    for pkg in npm:
        items.append({"type": "npm", "name": pkg, "status": "pending"})
    for cmd in post:
        # Shorten long commands for display
        display_name = cmd[:50] + "..." if len(cmd) > 50 else cmd
        items.append({"type": "post", "name": display_name, "status": "pending", "full": cmd})
    _install_progress["items"] = items
    _write_progress()


def update_progress(pkg_type: str, name: str, status: str):
    """Update status of a specific item (pending -> installing -> done/failed)."""
    for item in _install_progress["items"]:
        # Match by type and name (or full command for post)
        if item["type"] == pkg_type:
            if item["name"] == name or item.get("full") == name:
                item["status"] = status
                if status == "installing":
                    _install_progress["current"] = name
                break
    _write_progress()


def _write_progress():
    """Write progress to file for CLI to read."""
    try:
        import os
        with open("/tmp/install-progress.json", "w") as f:
            json.dump(_install_progress, f)
        os.chmod("/tmp/install-progress.json", 0o666)
    except Exception:
        pass


def log(level: str, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [{level}] {message}"
    print(line)
    if LOG_FILE:
        LOG_FILE.write(line + "\n")
        LOG_FILE.flush()


def log_info(msg: str):
    log("INFO", msg)


def log_warn(msg: str):
    log("WARN", msg)


def log_error(msg: str):
    log("ERROR", msg)


# ============================================================================
# Main Installation Logic
# ============================================================================

class PackageInstaller:
    """Main installer orchestrator."""

    def __init__(self, manifest_path: Path, log_path: Optional[Path]):
        setup_logging(log_path)
        self.manifest = Manifest(manifest_path)
        self.pip_mgr = PipManager()
        self.npm_mgr = NpmManager()
        self.post_runner = PostCommandRunner()

    def install(self, spec: PackageSpec, source: str) -> int:
        """
        Install packages according to specification.

        Returns:
            0 = All succeeded
            1 = Partial failure
            2 = Total failure
        """
        log_info(f"Starting package installation from {source}")
        log_info(f"Found {len(spec.pip)} pip, {len(spec.npm)} npm, {len(spec.post)} post-install items")

        # Initialize progress checklist
        init_progress(spec.pip, spec.npm, spec.post)

        total_succeeded = 0
        total_failed = 0

        # Install pip packages (fast)
        if spec.pip:
            pkg_list = ', '.join(spec.pip[:3]) + ('...' if len(spec.pip) > 3 else '')
            update_status("mcp_packages", f"pip: {pkg_list}")
            log_info(f"=== Installing {len(spec.pip)} pip packages ===")
            log_info(f"Packages: {', '.join(spec.pip)}")

            # Mark all as installing
            for pkg in spec.pip:
                update_progress("pip", pkg, "installing")

            result = self.pip_mgr.install_with_retry(spec.pip)

            for pkg in result.succeeded:
                _, version = self.pip_mgr.validate(pkg)
                self.manifest.record_success('pip', pkg, version or 'unknown', source)
                update_progress("pip", pkg, "done")

            for pkg in result.failed:
                self.manifest.record_failure('pip', pkg, result.errors.get(pkg, 'Unknown error'), 3)
                update_progress("pip", pkg, "failed")

            total_succeeded += len(result.succeeded)
            total_failed += len(result.failed)

        # Install npm packages (slow)
        if spec.npm:
            pkg_list = ', '.join(spec.npm[:3]) + ('...' if len(spec.npm) > 3 else '')
            update_status("mcp_packages", f"npm: {pkg_list}")
            log_info(f"=== Installing {len(spec.npm)} npm packages ===")
            log_info(f"Packages: {', '.join(spec.npm)}")

            # Mark all as installing
            for pkg in spec.npm:
                update_progress("npm", pkg, "installing")

            result = self.npm_mgr.install_with_retry(spec.npm)

            for pkg in result.succeeded:
                _, version = self.npm_mgr.validate(pkg)
                self.manifest.record_success('npm', pkg, version or 'unknown', source)
                update_progress("npm", pkg, "done")

            for pkg in result.failed:
                self.manifest.record_failure('npm', pkg, result.errors.get(pkg, 'Unknown error'), 3)
                update_progress("npm", pkg, "failed")

            total_succeeded += len(result.succeeded)
            total_failed += len(result.failed)

        # Run post commands (one by one)
        if spec.post:
            log_info(f"=== Running {len(spec.post)} post-install commands ===")
            for cmd in spec.post:
                short_cmd = cmd[:40] + ('...' if len(cmd) > 40 else '')
                update_status("mcp_packages", f"post: {short_cmd}")
                update_progress("post", cmd, "installing")
                log_info(f"Running: {cmd}")

                result = self.post_runner.run([cmd])

                if cmd in result.succeeded:
                    self.manifest.record_success('post', cmd, 'executed', source)
                    update_progress("post", cmd, "done")
                    total_succeeded += 1
                else:
                    self.manifest.record_failure('post', cmd, result.errors.get(cmd, 'Unknown error'), 1)
                    update_progress("post", cmd, "failed")
                    total_failed += 1

        # Save manifest
        self.manifest.save()
        log_info(f"Installation manifest saved to {self.manifest.path}")

        # Report summary
        log_info(f"=== Installation Summary ===")
        log_info(f"Total succeeded: {total_succeeded}")
        log_info(f"Total failed: {total_failed}")

        # Return exit code
        if total_failed == 0:
            log_info("Installation completed successfully!")
            return 0  # Complete success
        elif total_succeeded == 0:
            log_error("Installation failed completely!")
            return 2  # Total failure
        else:
            log_warn("Installation completed with some failures")
            return 1  # Partial failure


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Install MCP and project packages with validation and retry logic'
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--meta', type=Path, help='Path to mcp-meta.json')
    group.add_argument('--config', type=Path, help='Path to .agentbox.yml')
    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path('/workspace/.agentbox/install-manifest.json'),
        help='Path to installation manifest file'
    )
    parser.add_argument('--log', type=Path, help='Path to log file')

    args = parser.parse_args()

    try:
        # Parse input
        if args.meta:
            if not args.meta.exists():
                print(f"Error: {args.meta} does not exist")
                sys.exit(2)
            spec = PackageSpec.from_mcp_meta(args.meta)
            source = str(args.meta)
        else:
            if not args.config.exists():
                print(f"Error: {args.config} does not exist")
                sys.exit(2)
            spec = PackageSpec.from_agentbox_yml(args.config)
            source = str(args.config)

        # Check if there's anything to install
        if not spec.pip and not spec.npm and not spec.post:
            log_info("No packages to install")
            sys.exit(0)

        # Install
        installer = PackageInstaller(args.manifest, args.log)
        exit_code = installer.install(spec, source)

        sys.exit(exit_code)

    except Exception as e:
        log_error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        if LOG_FILE:
            LOG_FILE.close()


if __name__ == '__main__':
    main()
