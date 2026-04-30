"""Risk classification for MCP commands (100F). Deterministic heuristics — no execution."""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


_DANGEROUS_FRAGMENTS = (
    "rm -rf",
    "sudo ",
    "curl ",
    "wget ",
    "| sh",
    "| bash",
    "> /dev/",
    "mkfs",
    "dd if=",
    ":(){",
    "chmod -R 777",
)


def classify_risk(*, command: str) -> tuple[RiskLevel, str]:
    """Return risk tier and short rationale (for audits)."""
    raw = command.strip()
    lower = raw.lower()

    if "trident_force_high" in lower:
        return RiskLevel.HIGH, "marker_trident_force_high"

    if any(tok in lower for tok in _DANGEROUS_FRAGMENTS):
        return RiskLevel.HIGH, "matched_dangerous_fragment"

    if raw.startswith("pytest") or "trident_force_low" in lower:
        return RiskLevel.LOW, "safe_pattern_or_marker_trident_force_low"

    return RiskLevel.MEDIUM, "default_medium"
