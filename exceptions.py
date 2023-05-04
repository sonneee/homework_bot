class TokenDoesNotExist(Exception):
    """Отсутствует токен."""

    pass


class APIResponseError(Exception):
    """Ошибка ответа API."""

    pass


class WrongHomeworkStatus(Exception):
    """Неизвестный статус домашней работы."""

    pass


class NoHomeworkNameError(Exception):
    """Отстутствует ключ 'homework_name' в ответе API."""

    pass
