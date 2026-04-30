"""SSH adapter stub — returns synthetic output only (no network, no SSH)."""

from __future__ import annotations


def simulate_stub(*, command: str, target: str) -> dict[str, str | int]:
    trimmed = command.strip()[:4000]
    return {
        "adapter": "ssh_stub",
        "stdout": f"[simulated-ssh-stub] no remote execution; intent recorded ({len(trimmed)} chars)",
        "stderr": "",
        "exit_code": 0,
    }
