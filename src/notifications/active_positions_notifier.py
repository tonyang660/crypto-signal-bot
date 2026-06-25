import json
from pathlib import Path

import requests
from datetime import datetime
from typing import List, Optional

from loguru import logger

from src.core.config import Config


class ActivePositionsNotifier:
    """Send active position snapshots to a dedicated Discord webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or Config.ACTIVE_POSITIONS_WEBHOOK_URL
        self.state_file = Path(Config.DATA_DIR) / "active_positions_webhook_state.json"

    @staticmethod
    def _chunk_summary(summary: str, max_chars: int = 3800) -> List[str]:
        """Split long summaries so each Discord embed description stays valid."""
        if len(summary) <= max_chars:
            return [summary]

        chunks = []
        current = []
        current_len = 0

        for line in summary.splitlines():
            line_len = len(line) + 1
            if current and current_len + line_len > max_chars:
                chunks.append("\n".join(current))
                current = []
                current_len = 0

            if line_len > max_chars:
                chunks.append(line[:max_chars])
                continue

            current.append(line)
            current_len += line_len

        if current:
            chunks.append("\n".join(current))

        return chunks

    def _load_previous_message_id(self) -> Optional[str]:
        try:
            if not self.state_file.exists():
                return None

            with open(self.state_file, "r") as f:
                state = json.load(f)

            message_id = state.get("message_id")
            return str(message_id) if message_id else None

        except Exception as e:
            logger.warning(f"Could not load active positions webhook state: {e}")
            return None

    def _save_message_id(self, message_id: str):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "message_id": message_id,
                "updated_at": datetime.utcnow().isoformat()
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.warning(f"Could not save active positions webhook state: {e}")

    def _delete_message(self, message_id: str) -> bool:
        try:
            delete_url = f"{self.webhook_url}/messages/{message_id}"
            response = requests.delete(delete_url, timeout=15)

            if response.status_code in (204, 404):
                return True

            logger.warning(f"Could not delete previous active positions message: {response.status_code}")
            return False

        except Exception as e:
            logger.warning(f"Error deleting previous active positions message: {e}")
            return False

    def send_active_positions(self, summary: str, active_count: int) -> bool:
        """Send current active positions summary to the dedicated webhook."""
        if not self.webhook_url:
            logger.debug("Active positions webhook not configured; skipping Discord snapshot")
            return False

        try:
            color = 0x5865F2 if active_count else 0x808080
            chunks = self._chunk_summary(summary)
            embeds = []

            for index, chunk in enumerate(chunks[:10], start=1):
                title = f"Active Positions ({active_count})"
                if len(chunks) > 1:
                    title = f"{title} - Part {index}/{min(len(chunks), 10)}"

                embeds.append({
                    "title": title,
                    "description": f"```text\n{chunk}\n```",
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat(),
                    "footer": {
                        "text": "BitGet Futures Signal Bot"
                    }
                })

            payload = {
                "embeds": embeds,
                "allowed_mentions": {"parse": []}
            }

            previous_message_id = self._load_previous_message_id()
            response = requests.post(
                self.webhook_url,
                params={"wait": "true"},
                json=payload,
                timeout=15
            )

            if response.status_code == 200:
                message = response.json()
                message_id = str(message.get("id", ""))

                if not message_id:
                    logger.warning("Active positions snapshot sent, but Discord did not return a message ID")
                    return True

                self._save_message_id(message_id)
                if previous_message_id and previous_message_id != message_id:
                    self._delete_message(previous_message_id)

                logger.info(f"Active positions snapshot sent ({active_count} active)")
                return True

            logger.error(f"Failed to send active positions snapshot: {response.status_code}")
            return False

        except Exception as e:
            logger.error(f"Error sending active positions snapshot: {e}")
            return False
