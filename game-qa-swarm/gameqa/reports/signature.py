"""Signature helpers: stable, seed-independent keys used to merge duplicates."""
from __future__ import annotations

import hashlib
import re

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def stable_signature(kind, *parts):
    """Build `kind|part|part...`, dropping empty parts."""
    kept = [str(p) for p in parts if p not in (None, "")]
    return "|".join([kind] + kept)


def kind_of(signature):
    return signature.split("|", 1)[0]


def safe_filename(signature, max_len=80):
    """Filesystem-safe name for a signature, with a short hash for uniqueness."""
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:8]
    stem = _UNSAFE.sub("_", signature).strip("_")
    if len(stem) > max_len:
        stem = stem[:max_len]
    return "%s-%s" % (stem or "bug", digest)


def from_finding(finding):
    return finding.signature
