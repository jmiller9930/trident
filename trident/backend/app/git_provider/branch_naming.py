"""Canonical branch naming for Trident directives.

Standard:  trident/{directive_id_short}/{slug}
Example:   trident/d3f1a2b4/add-model-router

Enforced globally; directive integration must always call directive_branch_name().
"""

from __future__ import annotations

import re
import uuid

_SLUG_SAFE = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LEN = 40


def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric runs with hyphens, trim."""
    slug = _SLUG_SAFE.sub("-", text.lower()).strip("-")
    return slug[:_MAX_SLUG_LEN].strip("-") or "work"


def directive_branch_name(directive_id: uuid.UUID, title: str = "") -> str:
    """Return the canonical branch name for a directive.

    Format: trident/{first-8-hex-chars-of-directive-id}/{slug}

    Args:
        directive_id: The directive UUID.
        title: Human-readable title used to build the slug.
               Falls back to 'work' if empty or unparseable.

    Examples:
        directive_branch_name(UUID('d3f1a2b4-...'), 'Add model router')
        → 'trident/d3f1a2b4/add-model-router'
    """
    short_id = str(directive_id).replace("-", "")[:8]
    slug = _slugify(title) if title else "work"
    return f"trident/{short_id}/{slug}"


def validate_trident_branch_name(branch_name: str) -> bool:
    """Return True if branch_name follows the trident/{id}/{slug} convention."""
    parts = branch_name.split("/")
    if len(parts) < 3:
        return False
    if parts[0] != "trident":
        return False
    if not re.match(r"^[0-9a-f]{8}$", parts[1]):
        return False
    return True
