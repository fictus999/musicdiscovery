class ProviderUnavailableError(Exception):
    """A provider is unreachable or returned a failure (timeout, 5xx, network).

    Callers must catch this and degrade (V2.2 §8: no provider outage may
    break core discovery) rather than let it propagate to the request.
    """

    def __init__(self, provider: str, detail: str = ""):
        self.provider = provider
        self.detail = detail
        super().__init__(f"{provider} unavailable: {detail}" if detail else f"{provider} unavailable")


class ProviderCapabilityError(Exception):
    """Raised when code asks a provider adapter to perform an operation its
    declared ProviderCapabilities says it doesn't support — a programming
    error, not a runtime/network failure, so it is never meant to be caught
    and degraded the way ProviderUnavailableError is.
    """

    def __init__(self, provider: str, operation: str):
        self.provider = provider
        self.operation = operation
        super().__init__(f"{provider} does not support operation '{operation}'")
