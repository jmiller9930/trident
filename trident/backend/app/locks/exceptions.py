"""Lock / git governance errors (100E)."""


class LockConflictError(Exception):
    """Another active lock holds (project_id, file_path)."""

    pass


class LockNotFoundError(Exception):
    """No matching active lock."""

    pass


class LockOwnershipError(Exception):
    """Lock exists but directive_id / agent_role / user_id mismatch."""

    pass


class PathSafetyError(Exception):
    """Path escapes allowed project root or uses forbidden segments."""

    pass


class GitValidationError(Exception):
    """Repository validation or read-only git operation failed."""

    pass
