"""Exit codes from the design (SDD section 9): 0 success, 1 general, 2 usage, 3 auth, 4 conflict."""

GENERAL, USAGE, AUTH, CONFLICT = 1, 2, 3, 4


class CliError(Exception):
    def __init__(self, message: str, code: int = GENERAL):
        super().__init__(message)
        self.message = message
        self.code = code
