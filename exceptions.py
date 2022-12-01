class TokenError(Exception):
    """Ошибка токена."""
    pass


class StatusCodeError(Exception):
    """Код запроса отличается от 200."""
    pass
