"""Simulated local execution — never invokes the shell."""

from __future__ import annotations


def simulate(*, command: str, target: str) -> dict[str, str | int]:
    trimmed = command.strip()[:4000]
    return {
        "adapter": "local",
        "stdout": f"[simulated-local] no shell invoked; intent recorded ({len(trimmed)} chars)",
        "stderr": "",
        "exit_code": 0,
    }
