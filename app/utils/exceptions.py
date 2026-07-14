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
