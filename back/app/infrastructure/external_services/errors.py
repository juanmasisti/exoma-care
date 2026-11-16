class ExternalServiceError(RuntimeError):
    def __init__(self, service: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.service = service
        self.status_code = status_code
