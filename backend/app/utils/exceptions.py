"""Application-wide custom exceptions."""

class LLMTruncationError(Exception):
    """Raised when an LLM response is truncated due to length limits."""
    def __init__(self, message: str = "LLM response truncated due to context length limit", completion_tokens: int = 0):
        super().__init__(message)
        self.completion_tokens = completion_tokens
