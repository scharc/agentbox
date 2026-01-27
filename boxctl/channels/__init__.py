# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Notification channel abstraction for Remote Q&A.

Provides a pluggable system for two-way notifications. Channels can send
questions and poll for answers.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from boxctl.remote_qa import PendingQuestion

__all__ = ["NotificationChannel"]


class NotificationChannel(ABC):
    """Base class for two-way notification channels.

    Implement this to add custom notification channels (Slack, Discord, etc.).

    Example:
        class SlackChannel(NotificationChannel):
            def __init__(self, webhook_url: str):
                self.webhook_url = webhook_url

            @property
            def name(self) -> str:
                return "slack"

            def send_question(self, question: PendingQuestion) -> bool:
                # POST to Slack webhook
                ...

            def poll_answers(self) -> List[Tuple[str, str]]:
                return []  # Slack webhooks are outbound-only
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name for logging."""
        pass

    @abstractmethod
    def send_question(self, question: "PendingQuestion") -> bool:
        """Send notification for a question.

        Args:
            question: The pending question to notify about.

        Returns:
            True if the notification was sent successfully.
        """
        pass

    @abstractmethod
    def poll_answers(self) -> List[Tuple[str, str]]:
        """Poll for answers from this channel.

        Returns:
            List of (question_id, answer) tuples for any received answers.
        """
        pass

    def send_reply(self, text: str) -> None:
        """Send a reply/confirmation message (optional).

        Override this to send confirmation messages when answers are processed.

        Args:
            text: The reply text to send.
        """
        pass
