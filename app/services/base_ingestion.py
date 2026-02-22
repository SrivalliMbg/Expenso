"""
Abstract base for ingestion services (email, future SMS).
Pipeline uses: fetch_messages() -> list of { "id", "text" }.
Source-agnostic; parser and persistence stay the same.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class BaseIngestionService(ABC):
    """Abstract: fetch messages for a user. Returns normalized list for filtering/parsing."""

    def __init__(self, app, user_id: int):
        self.app = app
        self.user_id = user_id

    @abstractmethod
    def fetch_messages(
        self,
        after_date: Optional[datetime] = None,
        max_results: int = 50,
        **kwargs,
    ) -> List[dict]:
        """
        Fetch messages. Each item must have at least:
          - "id": str (external message id for dedup)
          - "text": str (combined subject + body for parser)
        Optional: subject, snippet, body_text for logging.
        """
        pass
