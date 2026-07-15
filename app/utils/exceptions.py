class BaseServiceException(Exception):
    error_code = 1000
    status_code = 500

    def __init__(self, message=None, error_code=None, status_code=None):
        if message:
            self.message = message
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code
        super().__init__()

    def as_dict(self) -> dict:
        return {
            'code': self.error_code,
            'message': self.message,
        }


class InvalidInputException(BaseServiceException):
    error_code = 1003
    message = 'Invalid input in request, please check again'
    status_code = 400

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NotEnoughDataException(BaseServiceException):
    error_code = 1004
    message = 'Not enough data found for processing'
    status_code = 422

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DataValidationException(BaseServiceException):
    error_code = 1005
    message = 'Invalid data or format found'
    status_code = 422

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class MobilityApiError(Exception):
    """Raised by the mobility feature routers (Shortlist/Candidate/Decision/Consent/Planning/
    Tracking/Outcomes) for a JSON:API-style error body — `{"errors": [{"detail": ...}]}` —
    instead of BaseServiceException's `{"error": {"code", "message"}}` shape. The frontend reads
    `error.errors[0].detail` (see TransitionPlanning.vue's initiatePlan 409 handling), so every
    mutation in this feature family raises this rather than a bare HTTPException."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
