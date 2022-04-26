import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Dict, List, Union

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (CheckHomeworksInResponse, CheckHomeworkStatus,
                        CheckStatusEndpoint)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

status_all_homeworks = {}


def init_logger() -> logging.Logger:
    """Настройки и инициализация логгера."""
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = init_logger()


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    return all([
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ])


def get_api_answer(current_timestamp: int) -> Dict[str, Union[list, int]]:
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise CheckStatusEndpoint(f'requests.get вернул ошибку "{error}"')
    if response.status_code != HTTPStatus.OK:
        message_error = (f'Недоступность эндпоига, '
                         f'статус кода: {response.status_code}')
        raise CheckStatusEndpoint(message_error)
    try:
        check_response = response.json()
    except AttributeError:
        raise CheckStatusEndpoint('Cервер вернул тело не в json формате')
    return check_response


def check_response(
            response: Dict[str, Union[str, int]]
        ) -> List[Dict[str, Union[str, int]]]:
    """Проверка ответ API на корректность."""
    if not isinstance(response, dict):
        message_error = 'API не корректен, response не является словарем'
        raise TypeError(message_error)
    if 'homeworks' not in response:
        message_error = 'API не корректен, в response отсутствует homeworks'
        raise CheckHomeworksInResponse(message_error)
    if not isinstance(response.get('homeworks'), list):
        message_error = 'API не корректен, response вернул не список'
        raise CheckHomeworksInResponse(message_error)
    return response.get('homeworks')


def parse_status(homework: Dict[str, Union[str, int]]) -> str:
    """информации о конкретной домашней работе, статус этой работы."""
    if 'homework_name' not in homework:
        message_error = ('Ошибка проверка статуса домашней работы, '
                         'отсутствует искомый ключ "homework_name"')
        raise KeyError(message_error)
    if 'status' not in homework:
        message_error = ('Ошибка проверка статуса домашней работы, '
                         'отсутствует искомый ключ "status"')
        raise KeyError(message_error)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        message_error = (f'Ошибка проверка статуса домашней работы, '
                         f'недокументированный статус: {homework_status}')
        raise CheckHomeworkStatus(message_error)
    if homework_name not in status_all_homeworks:
        status_all_homeworks[homework_name] = homework_status
        verdict = HOMEWORK_STATUSES[homework_status]
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    if homework_status != status_all_homeworks[homework_name]:
        status_all_homeworks[homework_name] = homework_status
        verdict = HOMEWORK_STATUSES[homework_status]
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    message = (f'Cтатус домашней "{homework_name}" '
               f'работы, не изменился')
    logger.debug(message)


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение успешно отправлено в Telegram: {message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствуют необходимые переменные окружения'
        logger.critical(message)
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    chek_send_message_error = False
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks_list = check_response(response)
            for homework_dict in homeworks_list:
                verdict_status = parse_status(homework_dict)
                if verdict_status is not None:
                    send_message(bot, verdict_status)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if not chek_send_message_error:
                send_message(bot, message)
                chek_send_message_error = True
        finally:
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time())


if __name__ == '__main__':
    main()
