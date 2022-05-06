import logging
import os
import sys
import time
from http import HTTPStatus
from json.decoder import JSONDecodeError
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    filename='runtime_log.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s; %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s; %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TIME_SIGNATURE_UNIX = 60 * 10
RETRY_TIME = 60 * 10
RETRY_TIME_AFTER_ERROR = 60

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot: telegram.Bot, message: str) -> None:
    """Bot message sender."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        info_message = 'Message is sent successfully!'
        logger.info(info_message)
    except telegram.TelegramError:
        error_message = 'Message cannot be sent.'
        logger.error(error_message)


def get_api_answer(current_timestamp: int) -> dict:
    """Checks api answer and get needed data after."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.ConnectionError:
        error_message = 'Endpoint is unreachable. Try another url.'
        logger.error(error_message)
        raise ConnectionError
    if response.status_code != HTTPStatus.OK:
        logger.error(
            f'Cannot access to api. '
            f'Status code: {response.status_code}'
        )
        raise response.raise_for_status()
    try:
        return response.json()
    except JSONDecodeError as error:
        logger.error(
            f'Cannon transform JSON data to python dict type: {error}'
        )
        raise JSONDecodeError


def check_response(response: dict) -> list:
    """Checks if api answer is correct."""
    if not isinstance(response, dict):
        error_message = 'API answer is not a valid.'
        logger.error(error_message)
        raise TypeError(error_message)
    try:
        lst_of_homeworks = response['homeworks']
    except KeyError:
        error_message = (
            'Somehow there is no key named "homeworks" in the data.'
        )
        logger.error(error_message)
        raise KeyError(error_message)
    if not isinstance(lst_of_homeworks, list):
        message = 'List of homeworks is not actually a list!'
        logger.error(message)
        raise TypeError(message)
    return lst_of_homeworks


def parse_status(homework: dict) -> str:
    """Checks that data after api answer is valid.
    And figures out the condition of 'status' parameter
    if it is clearly found.
    """
    try:
        homework_name = homework['homework_name']
    except KeyError:
        error_message = (
            'Cannot access to homework_name via key word "homework_name".'
        )
        logger.error(error_message)
        raise KeyError(error_message)
    try:
        homework_status = homework['status']
    except KeyError:
        error_message = (
            'Cannot access to status via key word "status".'
        )
        logger.error(error_message)
        raise KeyError(error_message)
    if homework_status not in HOMEWORK_STATUSES:
        error_message = 'There is not valid value of homework status.'
        logger.error(error_message)
        raise KeyError(error_message)
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_list_of_homeworks(homeworks: list) -> bool:
    """Function that inspects if list of homeworks empty or not."""
    if not isinstance(homeworks, list):
        error_message = 'Function expects list as an argument.'
        logger.error(error_message)
        raise TypeError(error_message)
    if len(homeworks) > 0:
        return True
    return False


def check_tokens() -> bool:
    """Checks tokens are accurately placed and flags if opposite."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    return False


def main() -> None:
    """The bot's main logic."""
    homeworks = []
    errors = []
    start_message = 'Searching for updates...'
    token_error_name = (
        'Some tokens or all of them are missed! '
        'Check that you have specified tokens and retry!'
    )
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.critical(
            msg=token_error_name
        )
        raise KeyError(token_error_name)
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.InvalidToken:
        logger.error('Telegram token is invalid!')
        raise telegram.error.InvalidToken
    send_message(bot, start_message)
    while True:
        try:
            response = get_api_answer(current_timestamp - TIME_SIGNATURE_UNIX)
            lst_of_homeworks = check_response(response)
            list_bool = check_list_of_homeworks(lst_of_homeworks)
            if list_bool:
                status = parse_status(lst_of_homeworks[0])
                if status not in homeworks:
                    homeworks.append(status)
                    send_message(bot, status)
            errors.clear()
            time.sleep(RETRY_TIME)
        except Exception as e:
            message = f'Programm failure! \n {e}'
            logger.error(message)
            if e.__repr__() not in errors:
                errors.append(e.__repr__())
                send_message(bot, message)
            time.sleep(RETRY_TIME_AFTER_ERROR)


if __name__ == '__main__':
    main()
