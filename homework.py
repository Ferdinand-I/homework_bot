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
# Добавил переменную с количеством секунд для ретрая после ошибки в main()
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

try:
    bot_for_sendings_error = telegram.Bot(token=TELEGRAM_TOKEN)
except telegram.error.InvalidToken:
    logger.error('Telegram token is invalid. Check this carefully!'
                 'Bot will not be able to send an error messages!')

API_ERROR_MESSAGE_COUNT = 0
CHECK_RESPONSE_ERROR_MESSAGE_COUNT = 0
CHECK_RESPONSE_ISINSTANCE_COUNT = 0


def send_message(bot: telegram.Bot, message: str) -> None:
    """Bot message sender."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info('Message is sent successfully!')
    except telegram.TelegramError as e:
        logger.error(f'Message cannot be sent: {e}')


def get_api_answer(current_timestamp: int) -> dict:
    """Checks api answer and get needed data after."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    response = None
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.ConnectionError:
        message = 'Endpoint is unreachable. Try another url.'
        logger.error(message)
        send_message(
            bot_for_sendings_error,
            message
        )
    if response.status_code != HTTPStatus.OK:
        global API_ERROR_MESSAGE_COUNT
        API_ERROR_MESSAGE_COUNT += 1
        logger.error(
            f'Cannot access to api. '
            f'Status code: {response.status_code}'
        )
        # Отправляем сообщение в телеграм только когда счётчик  == 1
        #  При этом логгируем каждое такое событие
        if API_ERROR_MESSAGE_COUNT == 1:
            send_message(
                bot_for_sendings_error,
                message='Error message: Cannot access to api.'
            )
        raise response.raise_for_status()
    API_ERROR_MESSAGE_COUNT = 0
    try:
        return response.json()
    except JSONDecodeError as error:
        logger.error(
            f'Cannon transform JSON data to python dict type: {error}'
        )


def check_response(response: dict) -> list:
    """Checks if api answer is correct."""
    try:
        response['homeworks']
    except KeyError as e:
        global CHECK_RESPONSE_ERROR_MESSAGE_COUNT
        CHECK_RESPONSE_ERROR_MESSAGE_COUNT += 1
        logger.error(f'There is no key {e}')
        if CHECK_RESPONSE_ERROR_MESSAGE_COUNT == 1:
            send_message(
                bot=bot_for_sendings_error,
                message='Cannot find you homeworks while parsing api :('
            )
        raise KeyError
    lst_of_homeworks = response['homeworks']
    if not isinstance(lst_of_homeworks, list):
        global CHECK_RESPONSE_ISINSTANCE_COUNT
        CHECK_RESPONSE_ISINSTANCE_COUNT += 1
        message = 'List of homeworks is not actually a list!'
        logger.error(message)
        if CHECK_RESPONSE_ISINSTANCE_COUNT == 1:
            send_message(
                bot=bot_for_sendings_error,
                message='Could not get a list of your homeworks'
            )
        raise TypeError(message)
    CHECK_RESPONSE_ISINSTANCE_COUNT = 0
    CHECK_RESPONSE_ERROR_MESSAGE_COUNT = 0
    return lst_of_homeworks


def parse_status(homework: dict) -> str:
    """Checks that data after api answer is valid.
    And figures out the condition of 'status' parameter
    if it is clearly found.
    """
    try:
        homework['homework_name']
    except KeyError as e:
        logger.error(
            f'Cannot access to homework_name via '
            f'"homework_name" key: {e}'
        )
    try:
        homework['status']
    except KeyError as e:
        logger.error(
            f'Cannot access to status via '
            f'"status" key: {e}'
        )
    if homework['status'] not in HOMEWORK_STATUSES:
        logger.error('There is not valid value.')
        raise KeyError
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Checks tokens are accurately placed and flags if opposite."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    return False


def main() -> None:
    """The bot's main logic."""
    token_error_name = (
        'Some tokens or all of them are missed! '
        'Check that you have specified tokens and retry!'
    )
    bot = None
    if not check_tokens():
        logger.critical(
            msg=token_error_name
        )
        raise KeyError('Required environment variable is missed!')
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
    except telegram.error.InvalidToken:
        logger.error('Telegram token is invalid!')
    current_timestamp = int(time.time())
    no_update_count = 0
    body_error_count = 0
    while True:
        try:
            response = get_api_answer(current_timestamp - TIME_SIGNATURE_UNIX)
            lst_of_update = check_response(response)
            if len(lst_of_update) > 0:
                no_update_count = 0
                send_message(bot, parse_status(lst_of_update[0]))
            else:
                no_update_count += 1
                if no_update_count == 1:
                    send_message(bot, 'There is no updates yet!')
            body_error_count = 0
            time.sleep(RETRY_TIME)
        except Exception:
            body_error_count += 1
            message = 'Programm failure!'
            logger.error(message)
            if body_error_count == 1:
                send_message(bot, message)
            time.sleep(RETRY_TIME_AFTER_ERROR)
        else:
            pass


if __name__ == '__main__':
    main()
