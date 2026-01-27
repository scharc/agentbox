# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Compatibility shim for the boxctl CLI entrypoint."""

from boxctl.cli import main as package_main


def main():
    """Main entry point."""
    package_main()


if __name__ == "__main__":
    main()
