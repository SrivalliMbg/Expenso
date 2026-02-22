"""
SMS ingestion service. Subclasses BaseIngestionService; reads from UploadedSMS (populated by POST /api/sms/upload).
Returns normalized list { "id", "text" } for the shared pipeline/parser.
"""
import logging
from datetime import datetime
from typing import List, Optional

from flask import current_app

from .base_ingestion import BaseIngestionService
from .constants import SMS_BODY_MAX_LENGTH

logger = logging.getLogger(__name__)


# Android integration: App should request READ_SMS permission, filter messages locally (e.g. by sender
# or date range), and send only recent SMS to POST /api/sms/upload to minimize payload and privacy surface.


class SMSIngestionService(BaseIngestionService):
    """
    Fetches messages from UploadedSMS for the given user. Optional after_date filters by SMS timestamp.
    Returns list of { "id": device_sms_id, "text": body } for parser/pipeline.
    """

    def fetch_messages(
        self,
        after_date: Optional[datetime] = None,
        max_results: int = 100,
        **kwargs,
    ) -> List[dict]:
        from app.models import UploadedSMS

        app = self.app or current_app
        if not app:
            return []

        q = UploadedSMS.query.filter(UploadedSMS.user_id == self.user_id)
        if after_date is not None:
            q = q.filter(UploadedSMS.timestamp >= after_date)
        rows = q.order_by(UploadedSMS.id.desc()).limit(max_results).all()

        out = []
        for row in rows:
            text = (row.body or "").strip()
            if len(text) > SMS_BODY_MAX_LENGTH:
                text = text[:SMS_BODY_MAX_LENGTH]
            out.append({"id": row.device_sms_id, "text": text})
        return out
