class ServerNotAvailable(Exception):
    """Сервер Яндекс API недоступен."""


class TokensNotAvailable(Exception):
    """Необходимые токены отсутствуют в окружении."""
