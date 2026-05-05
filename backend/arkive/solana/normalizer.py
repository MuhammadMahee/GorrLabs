"""Deterministic normalization helpers for Solana audit anchoring.

This module turns audit event payloads into canonical JSON before hashing.
The determinism contract is:

Same event_type + same payload with the same field names and same field
values always produces the same canonical string, and therefore always
produces the same SHA-256 hash.

Callers must remove non-deterministic fields before calling these helpers.
Examples include auto-generated timestamps, request-local IDs, random IDs
added after the fact, or any field whose value can change between otherwise
identical events. This module only makes serialization deterministic; it does
not decide which fields belong in a compliance payload.
"""

import hashlib
import json


def normalize_event(event_type: str, payload: dict) -> str:
    """Return canonical JSON for an audit event."""
    return json.dumps(
        {'event': event_type, 'data': payload},
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    )


def hash_event(canonical: str) -> str:
    """Return the SHA-256 hex digest for a canonical event string."""
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def normalize_and_hash(event_type: str, payload: dict) -> tuple[str, str]:
    """Return the canonical event string and its SHA-256 hex digest."""
    canonical = normalize_event(event_type, payload)
    return canonical, hash_event(canonical)
