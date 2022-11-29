import logging
import os
import requests
import telegram
import sys
import time
from exceptions import TelegramError
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

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream='sys.stdout')
logger.addHandler(handler)

def check_tokens():
    """Проверка наличия токенов."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправка сообщения об изменении статуса."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug('Отправляем сообщение в Telegram')
    except Exception as error:
        message = f'Сообщение не отправлено: {error}'
        logger.error(message)
    
def get_api_answer(timestamp):
    """Получаем ответ от API Практикума."""
    logger.info('Делаем запрос к API Практикума.')
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = f'Ошибка подключения к API: {error}'
        logger.error(message)
    if response.status_code != 200:
        raise ReferenceError('Статус ответа API не OK')
    return response.json()

def check_response(response):
    """Проверяет ответ API на корректность."""
    logger.info('Начало проверки на корректность')
    if not isinstance(response, dict):
        raise TypeError('В ответе API нет словаря')
    if 'homeworks' not in response:
        raise KeyError('Ключа "homeworks" в словаре нет')
    if not isinstance(response['homeworks'], list):
        raise TypeError('По ключу "homeworks" не получен список')
    return response['homeworks']

def parse_status(homework):
    """Извлекаем информацию о конкретной домашней работе."""
    logger.info('Извлекаем информацию о конкретной домашней работе.')
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ "homework_name"')
    status = homework['status']
    homework_name = homework['homework_name']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Неизвестный статус')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'

def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = (
            'Отсутствуют обязательные переменные окружения: '
            'TELEGRAM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID. '
            'Программа принудительно остановлена'
        )
        logger.critical(error_message)
        sys.exit(error_message)

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
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
