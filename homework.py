import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

from exceptions import (
    TokenDoesNotExist,
    APIResponseError,
    WrongHomeworkStatus,
    NoHomeworkNameError,
    NoStatusError
)


logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
handler.setFormatter(formatter)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        raise TokenDoesNotExist


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.debug('Попытка отправить сообщение')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение успешно отправлено')
    except TelegramError:
        logger.error('Не удалось отправить сообщение')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    logger.debug('Попытка выполнить запрос к API')
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params={'from_date': timestamp})
    except requests.RequestException:
        raise APIResponseError
    if homework_statuses.status_code != HTTPStatus.OK:
        raise APIResponseError
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError
    if 'homeworks' not in response.keys():
        raise TypeError
    if 'current_date' not in response.keys():
        raise TypeError
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError
    return homeworks


def parse_status(homework):
    """Возвращает статус домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if 'homework_name' not in homework.keys():
        raise NoHomeworkNameError
    if 'status' not in homework.keys():
        raise NoStatusError
    if status in HOMEWORK_VERDICTS.keys():
        verdict = HOMEWORK_VERDICTS.get(status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    raise WrongHomeworkStatus


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except TokenDoesNotExist:
        logger.critical('Отсутствуют переменные окружения')
        exit()

    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_homework = {}

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0 and last_homework != homeworks[0]:
                last_homework = homeworks[0]
                message = parse_status(last_homework)
                send_message(bot, message)
            else:
                logger.debug('Отсутствуют новые статусы')

        except (APIResponseError, TypeError, WrongHomeworkStatus) as error:
            message = f'Сбой в работе программы: {type(error).__doc__}'
            logger.error(message)
            send_message(bot, message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
