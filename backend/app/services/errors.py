class UpstreamError(Exception):
    """A data provider failed or was unreachable. The API maps this to HTTP 502."""

    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.detail = detail
