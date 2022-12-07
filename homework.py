import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import StatusCodeError, ResponseError


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

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

SEND_MESSAGE_INFO = 'Сообщение отправлено: "{}"'
NOT_SENT_MESSAGE_INFO = 'Сообщение "{}" не отправлено: "{}"'
API_INFO = 'Делаем запрос к API Практикума.'
API_ERROR = ('Ошибка подключения к API: {error}.'
             'endpoint: {url}, headers: {headers}, params: {params}')
STATUS_CODE_ERROR = ('Неверный ответ сервера {status_code}.'
                     'endpoint: {url}, headers: {headers}, params: {params}')
RESPONSE_ERROR = ('Отказ от обслуживания: {error}, key {key}. '
                  'endpoint: {url}, headers: {headers}, params: {params}')
RESPONSE_NOT_DICT = 'В ответе API не словарь, а {}'
HOMEWORKS_KEY_NOT_FOUND = 'Ключа "homeworks" в словаре нет'
HOMEWORKS_NOT_LIST = ('Под ключом "homeworks"'
                      'домашка приходит не в виде списка, а {}')
HOMEWORK_NAME_NOT_FOUND = 'Не найден ключ "homework_name"!'
UNKNOWN_STATUS = 'Неизвестный статус: {}'
STATUS_CHANGED = 'Изменился статус проверки работы "{name}". {verdict}'
ERROR_MESSAGE = 'Сбой в работе программы: {}'
CRITIKAL_ERROR = 'Отсутсвует или некорректна переменная: {token}'
CHECK_INFO = 'Начало проверки на корректность'
PARSE_INFO = 'Извлекаем информацию о конкретной домашней работе'
TOKEN_ERROR = 'Отсутствуют переменные окружения'


def send_message(bot, message):
    """Отправка сообщения об изменении статуса."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug(SEND_MESSAGE_INFO.format(message))
        return True
    except Exception as error:
        logging.exception(NOT_SENT_MESSAGE_INFO.format(message, error))
        return False


def get_api_answer(timestamp):
    """Получаем ответ от API Практикума."""
    logging.info(API_INFO)
    parameters = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        response = requests.get(**parameters)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(API_ERROR.format(error=error,
                                               **parameters))
    status_code = response.status_code
    if status_code != 200:
        raise StatusCodeError(STATUS_CODE_ERROR.format(status_code=status_code,
                                                       **parameters))
    response_json = response.json()
    for key in ('error', 'code'):
        if key in response_json:
            raise ResponseError(RESPONSE_ERROR.format(
                error=response_json[key],
                key=key,
                **parameters))
    return response_json


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.info(CHECK_INFO)
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_NOT_DICT.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_KEY_NOT_FOUND)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORKS_NOT_LIST.format(type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлекаем информацию о конкретной домашней работе."""
    logging.info(PARSE_INFO)
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNKNOWN_STATUS.format(status))
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_NOT_FOUND)
    return STATUS_CHANGED.format(
        name=homework['homework_name'],
        verdict=HOMEWORK_VERDICTS[status])


def check_tokens():
    """Проверка наличия токенов."""
    token_list = [name for name in TOKENS if globals()[name] is None]
    if token_list:
        logging.critical(CRITIKAL_ERROR.format(token=token_list))
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(TOKEN_ERROR)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                if send_message(bot, parse_status(homeworks[0])):
                    timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logging.exception(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
        handlers=[
            logging.StreamHandler(stream=sys.stdout),
            logging.FileHandler(__file__ + '.log')],
    )
    main()
