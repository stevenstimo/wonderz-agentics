"""
Email Intake Channel §4.1: IMAP polling of Gmail inbox.
UNSEEN emails: fetch → parse → process (only then mark \\Seen so failed emails are retried next poll).
All imaplib calls run in asyncio.to_thread() so the event loop is never blocked.
"""

import asyncio
import email
import imaplib
import logging
import os
from typing import List, Tuple

from app.services.email_parser import EmailParser
from app.services.inbox_engine import InboxEngine

logger = logging.getLogger(__name__)

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
DEFAULT_POLL_INTERVAL = 60


def _sync_fetch_unseen(gmail_address: str, app_password: str) -> List[Tuple[bytes, bytes]]:
    """
    Run in thread: connect, search UNSEEN by UID, fetch each RFC822.
    Returns list of (uid, raw_bytes). Uses UID so we can mark \\Seen later by UID.
    """
    result: List[Tuple[bytes, bytes]] = []
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
        imap.login(gmail_address, app_password)
        imap.select("INBOX")
        typ, data = imap.uid("SEARCH", None, "UNSEEN")
        if typ != "OK" or not data or not data[0]:
            return result
        uids = data[0].split()
        for uid in uids:
            typ, fetch_data = imap.uid("FETCH", uid, "(RFC822)")
            if typ != "OK" or not fetch_data:
                continue
            part = fetch_data[0]
            if isinstance(part, tuple) and len(part) >= 2:
                raw = part[1]
                if isinstance(raw, bytes):
                    result.append((uid, raw))
                elif isinstance(raw, str):
                    result.append((uid, raw.encode("utf-8", errors="replace")))
            elif isinstance(part, bytes):
                result.append((uid, part))
    return result


def _sync_mark_seen(gmail_address: str, app_password: str, uids: List[bytes]) -> None:
    """Run in thread: connect, store +FLAGS \\Seen for each UID. Only call after process() succeeded."""
    if not uids:
        return
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
        imap.login(gmail_address, app_password)
        imap.select("INBOX")
        for uid in uids:
            try:
                imap.uid("STORE", uid, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.warning("EmailPoller: failed to mark UID %s as Seen: %s", uid, e)


class EmailPoller:
    """Poll Gmail for UNSEEN emails; parse and process; mark \\Seen only after successful process."""

    def __init__(
        self,
        gmail_address: str,
        app_password: str,
        poll_interval_seconds: int | None = None,
    ):
        self.gmail_address = gmail_address
        self.app_password = app_password
        self.poll_interval = poll_interval_seconds or int(
            os.getenv("EMAIL_POLL_INTERVAL", DEFAULT_POLL_INTERVAL)
        )

    async def poll_loop(self) -> None:
        """Main loop: poll every poll_interval, process UNSEEN, never block event loop."""
        while True:
            try:
                await self.poll_once()
            except Exception as e:
                logger.exception("EmailPoller error: %s", e)
            await asyncio.sleep(self.poll_interval)

    async def poll_once(self) -> None:
        """
        One poll cycle: fetch UNSEEN (in thread) → for each message: parse, await process(),
        then mark \\Seen only for messages that were processed successfully.
        """
        logger.debug("EmailPoller: poll_once starting IMAP fetch")
        uid_raw_list = await asyncio.to_thread(
            _sync_fetch_unseen,
            self.gmail_address,
            self.app_password,
        )
        logger.debug("EmailPoller: fetched %d unseen emails", len(uid_raw_list))
        if not uid_raw_list:
            return
        to_mark_seen: List[bytes] = []
        for uid, raw in uid_raw_list:
            try:
                msg = email.message_from_bytes(raw)
                parsed = EmailParser.parse(msg)
                logger.info("EmailPoller: processing UID %s from=%s subject=%s", uid, parsed.get('from', '?'), parsed.get('subject', '?'))
                await InboxEngine.process(parsed)
                logger.info("EmailPoller: UID %s processed OK, marking Seen", uid)
                to_mark_seen.append(uid)
            except Exception as e:
                logger.warning(
                    "EmailPoller: skip marking Seen for UID %s (process failed: %s); will retry next poll",
                    uid,
                    e,
                )
        if to_mark_seen:
            await asyncio.to_thread(
                _sync_mark_seen,
                self.gmail_address,
                self.app_password,
                to_mark_seen,
            )
