"""Agentctl - tmux session management for boxctl containers"""

from boxctl.agentctl.cli import cli


def main():
    """Main entry point for agentctl CLI"""
    return cli()


__all__ = ["main", "cli"]
