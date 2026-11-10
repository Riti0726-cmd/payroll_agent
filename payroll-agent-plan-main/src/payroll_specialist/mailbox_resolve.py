"""Resolve specialist mailbox for Neon queue/drafts/changelists filters."""

from __future__ import annotations


def resolve_specialist_mailbox(specialist_id: str, mailbox_override: str = "") -> str:
    """Prefer explicit mailbox override, then triage config, then specialist_id.

    Placeholder config values like ``mailbox-default`` are ignored so they do not
    hide Neon rows keyed by a real specialist email.
    """
    override = (mailbox_override or "").strip()
    if override:
        return override

    from store import get_triage_store

    config = get_triage_store().get_specialist_config(specialist_id) or {}
    mailbox = (config.get("mailbox_id") or config.get("mailbox") or "").strip()
    if mailbox and not mailbox.startswith("mailbox-"):
        return mailbox
    return (specialist_id or "").strip()
