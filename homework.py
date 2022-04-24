import os
import sys
import time
import logging

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (CheckHomeworksInResponse, CheckHomeworkStatus,
                        CheckStatusEndpoint, DebugHomeworkStatus)

load_dotenv()


logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


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


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_CHAT_ID is None
            or TELEGRAM_TOKEN is None):
        return False
    else:
        return True


def get_api_answer(current_timestamp) -> dict:
    """Запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        message_error = f'статус кода: {response.status_code}'
        raise CheckStatusEndpoint(message_error)
    return response.json()


def check_response(response) -> list:
    """Проверка ответ API на корректность."""
    if type(response) != dict:
        message_error = 'response не является словарем'
        raise TypeError(message_error)
    elif 'homeworks' not in response:
        message_error = 'в response отсутствует homeworks'
        raise CheckHomeworksInResponse(message_error)
    elif type(response.get('homeworks')) != list:
        message_error = 'response вернул не список'
        raise CheckHomeworksInResponse(message_error)
    else:
        return response.get('homeworks')


def parse_status(homework) -> str:
    """информации о конкретной домашней работе, статус этой работы."""
    if 'homework_name' and 'status' not in homework:
        message_error = 'отсутствуют искомые ключи'
        raise KeyError(message_error)
    else:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        message_error = f'недокументированный статус: {homework_status}'
        raise CheckHomeworkStatus(message_error)
    elif homework_name not in status_all_homeworks:
        status_all_homeworks[homework_name] = homework_status
        verdict = HOMEWORK_STATUSES[homework_status]
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    elif homework_status != status_all_homeworks[homework_name]:
        status_all_homeworks[homework_name] = homework_status
        verdict = HOMEWORK_STATUSES[homework_status]
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    else:
        raise DebugHomeworkStatus(homework_name)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение успешно отправлено в Telegram: {message}')
    except Exception as error:
        logger.error(f'Сбой при отправке сообщения в Telegram: {error}')


def chek_send_message_error(bot, message, send_message_error):
    """Проверка повторной отправки ошибки в Telegram."""
    if message in send_message_error:
        if send_message_error[message] is not True:
            send_message(bot, message)
            send_message_error[message] = True
    elif message not in send_message_error:
        send_message(bot, message)
        send_message_error[message] = True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствуют необходимые переменные окружения'
        logger.critical(message)
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    send_message_error = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
        except Exception as error:
            message = f'Недоступность эндпоига, {error}'
            logger.error(message)
            chek_send_message_error(bot, message, send_message_error)
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time())
            continue
        try:
            homeworks_list = check_response(response)
        except Exception as error:
            message = f'API не корректен, {error}'
            logger.error(message)
            chek_send_message_error(bot, message)
            time.sleep(RETRY_TIME)
            current_timestamp = int(time.time())
            continue
        # for numwork in range(0, len(homeworks_list)):
        try:
            verdict_status = parse_status(homeworks_list[0])
            send_message(bot, verdict_status)
        except DebugHomeworkStatus as error:
            message = (f'Cтатус домашней "{error}" '
                         f'работы, не изменился')
            logger.debug(message)
        except Exception as error:
            message = (f'Ошибка проверка статуса '
                       f'домашней работы, {error}')
            logger.error(message)
            chek_send_message_error(bot, message)
        time.sleep(RETRY_TIME)
        current_timestamp = int(time.time())
        send_message_error = {}


if __name__ == '__main__':
    main()
