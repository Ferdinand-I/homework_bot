import logging
import os
import sys
import time
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
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

bot_for_sendings_error = telegram.Bot(token=TELEGRAM_TOKEN)

API_ERROR_MESSAGE_COUNT = 0


def send_message(bot, message):
    """Bot message sender."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info('Message is sent successfully!')
    except Exception as error:
        logger.error(f'Message cannot sent: {error}')


def get_api_answer(current_timestamp: int) -> dict:
    """Checks api answer and get needed data after."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    response = requests.get(
        url=ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if response.status_code != 200:
        global API_ERROR_MESSAGE_COUNT
        API_ERROR_MESSAGE_COUNT += 1
        if API_ERROR_MESSAGE_COUNT == 1:
            logger.error('Cannot access to api.')
            send_message(
                bot_for_sendings_error,
                message='Error message: Cannot access to api.'
            )
        raise ValueError
    API_ERROR_MESSAGE_COUNT = 0
    try:
        response.json()
    except Exception as error:
        logger.error(f'Cannon transform data to python dict type: {error}')
    return response.json()


def check_response(response: dict) -> list:
    """Checks if api answer is correct."""
    try:
        response['homeworks']
    except Exception as error:
        logger.error(f'There is no key "homeworks: {error}')
    lst_of_homeworks = response['homeworks']
    if isinstance(lst_of_homeworks, list) is not True:
        logger.error('List of homeworks is not actually a list!')
        raise TypeError
    return lst_of_homeworks


def parse_status(homework: dict) -> str:
    """Checks that data after api answer is valid.
    And figures out the condition of 'status' parameter
    if it is clearly found.
    """
    try:
        homework['homework_name']
    except Exception as e:
        logger.error(
            f'Cannot access to homework_name via '
            f'"homework_name" key: {e}'
        )
    try:
        homework['status']
    except Exception as e:
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


def main():
    """The bot's main logic."""
    token_error_name = (
        'Some tokens or all of them are missed! '
        'Check that you have specified tokens!'
    )
    if check_tokens() is False:
        logger.critical(
            msg=token_error_name
        )
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        send_message(bot, token_error_name)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    no_update_count = 0
    body_error_count = 0
    while True:
        try:
            response = get_api_answer(current_timestamp - TIME_SIGNATURE_UNIX)
            lst_of_upadate = check_response(response)
            if len(lst_of_upadate) > 0:
                no_update_count = 0
                body_error_count = 0
                send_message(bot, parse_status(lst_of_upadate[0]))
            else:
                no_update_count += 1
                if no_update_count == 1:
                    send_message(bot, 'There is no updates yet!')
            time.sleep(RETRY_TIME)
        except Exception as error:
            body_error_count += 1
            message = f'Сбой в работе программы! {error}'
            if body_error_count == 1:
                try:
                    send_message(bot, message)
                except Exception as e:
                    logger.error(f'Bot cannot send an error message. {e}')
                time.sleep(RETRY_TIME)
        else:
            pass


if __name__ == '__main__':
    main()
