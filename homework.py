import sys
import os
import requests
import time
import logging

from http import HTTPStatus
from logging import StreamHandler
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

from exceptions import (
    TokenDoesNotExist,
    APIResponseError,
    WrongHomeworkStatus,
    NoHomeworkNameError
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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение успешно отправлено')
    except TelegramError:
        logger.error('Не удалось отправить сообщение')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
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
    expected_response = {
        'id': int,
        'status': str,
        'homework_name': str,
        'reviewer_comment': str,
        'date_updated': str,
        'lesson_name': str,
    }
    if isinstance(response, dict):
        homeworks = response.get('homeworks')
        if homeworks is None or not isinstance(homeworks, list):
            raise TypeError
        if not homeworks == []:
            for homework in homeworks:
                for key, value_type in expected_response.items():
                    value = homework.get(key)
                    if value is not None and not isinstance(value, value_type):
                        raise TypeError
    else:
        raise TypeError


def parse_status(homework):
    """Возвращает статус домашней работы."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise NoHomeworkNameError
    status = homework.get('status')
    if status in HOMEWORK_VERDICTS.keys():
        verdict = HOMEWORK_VERDICTS.get(status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
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
            check_response(response)
            homeworks = response.get('homeworks')
            if len(homeworks) > 0 and last_homework != homeworks[0]:
                last_homework = homeworks[0]
                message = parse_status(last_homework)
                send_message(bot, message)
            else:
                logger.debug('Отсутствуют новые статусы')

        except APIResponseError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        except TypeError as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        except WrongHomeworkStatus as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
