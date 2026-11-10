"""Assemble current-request text from email thread context (UC-012–014)."""

from __future__ import annotations


def assemble_current_request(
    *,
    subject: str,
    current_body: str,
    prior_bodies: list[str],
    max_prior: int = 10,
) -> str:
    """Build classifier input: subject + capped prior thread + current message.

    ``prior_bodies`` must be oldest → newest. Only the last ``max_prior`` are kept.
    """
    prior = prior_bodies[-max_prior:] if max_prior > 0 else []
    parts = [f"Subject: {(subject or '').strip()}"]
    if prior:
        parts.append("Prior thread (oldest to newest):")
        for i, body in enumerate(prior, 1):
            parts.append(f"[{i}] {(body or '').strip()[:2000]}")
    parts.append("Current message:")
    parts.append((current_body or "").strip())
    return "\n".join(parts).strip()
