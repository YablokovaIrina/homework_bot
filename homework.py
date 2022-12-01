import logging
import os
import time

import requests
import telegram

from exceptions import TokenError, StatusCodeError
from dotenv import load_dotenv

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

SEND_MESSAGE_INFO = 'Сообщение отправлено: "{}"'
NOT_SENT_MESSAGE_INFO = 'Сообщение не отправлено: "{}"'
API_INFO = 'Делаем запрос к API Практикума.'
API_ERROR = 'Ошибка подключения к API: {}'
RESPONSE_ERROR = 'Неверный ответ сервера {}. Параметры запроса: {}'
RESPONSE_NOT_DICT = 'В ответе API не словарь, а {}'
HOMEWORKS_KEY_NOT_FOUND = 'Ключа "homeworks" в словаре нет'
HW_NOT_LIST = 'Под ключом "homeworks" домашка приходит не в виде списка, а {}'
HOMEWORK_NAME_NOT_FOUND = 'Не найден ключ "homework_name"!'
ID_NOT_FOUND = 'Не найден ID пользователя'
TOKEN_TELEGRAM_NOT_FOUND = 'Токен telegram не найден'
TOKEN_PRACTICUM_NOT_FOUND = 'Токен Практикума не найден'
UNKNOWN_STATUS = 'Неизвестный статус: {}'
STATUS_CHANGED = 'Изменился статус проверки работы "{}". {}'
ERROR_MESSAGE = 'Сбой в работе программы: {}'
ERROR_SEND_MESSAGE = 'Ошибка при отправке сообщения: {}'
CRITIKAL_ERROR = 'Проблемы с переменными окружения'


def send_message(bot, message):
    """Отправка сообщения об изменении статуса."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug(SEND_MESSAGE_INFO.format(message))
    except Exception as error:
        logging.exception(NOT_SENT_MESSAGE_INFO.format(error))


def get_api_answer(timestamp):
    """Получаем ответ от API Практикума."""
    logging.info(API_INFO)
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        raise TypeError(API_ERROR.format(error))
    status_code = response.status_code
    if status_code != 200:
        raise StatusCodeError(RESPONSE_ERROR.format(ENDPOINT, params))
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.info('Начало проверки на корректность')
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_NOT_DICT.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_KEY_NOT_FOUND)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(HW_NOT_LIST.format(type(homeworks)))
    return response.get('homeworks')


def parse_status(homework):
    """Извлекаем информацию о конкретной домашней работе."""
    logging.info('Извлекаем информацию о конкретной домашней работе.')
    status = homework['status']
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_NOT_FOUND)
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNKNOWN_STATUS.format(status))
    return (STATUS_CHANGED.format(
        homework['homework_name'],
        HOMEWORK_VERDICTS.get(status)
    ))


def check_tokens():
    """Проверка наличия токенов."""
    if (PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        logging.critical(CRITIKAL_ERROR)
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = (
            'Отсутствуют обязательные переменные окружения: '
            'TELEGRAM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID. '
            'Программа принудительно остановлена'
        )
        raise TokenError(error_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            logging.exception(ERROR_MESSAGE.format(error))
            try:
                bot.send_message(TELEGRAM_CHAT_ID, ERROR_MESSAGE.format(error))
            except Exception as error:
                logging.exception(ERROR_SEND_MESSAGE.format(error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
        handlers = [
            logging.StreamHandler(stream='sys.stdout'),
            logging.FileHandler(__file__ + '.log')],
    )
    logger = logging.getLogger(__name__)
    main()
