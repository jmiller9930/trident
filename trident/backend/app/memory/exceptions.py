class MemoryWriteForbidden(Exception):
    """Raised when workflow context or RBAC checks fail for a memory write."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
