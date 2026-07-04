
class AIGatewayClientError(Exception):
    """Base exception for all AI Gateway client errors.

    Attributes:
        message: Human-readable, actionable error description.
                 MUST NOT contain secrets (API keys, tokens, passwords).
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

