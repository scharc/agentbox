"""Agentctl - tmux session management for agentbox containers"""

from agentbox.agentctl.cli import cli


def main():
    """Main entry point for agentctl CLI"""
    return cli()


__all__ = ["main", "cli"]
