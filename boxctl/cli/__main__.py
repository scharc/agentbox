# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Allow running boxctl CLI as a module: python -m boxctl.cli"""

from boxctl.cli import main

if __name__ == "__main__":
    main()
