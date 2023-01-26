import os
import sys
import logging
import time

import requests
import telegram
from dotenv import load_dotenv
from http import HTTPStatus

import exceptions

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS_TUPLE = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
# AssertionError: Не найдена переменная `ENDPOINT.
# Не удаляйте и не переименовывайте ее.
# Не дают другой нейминг использовать.
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] - %(message)s',
    level=logging.DEBUG,
)
logger = logging.getLogger('__name__')
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверяет доступны ли токены в окружении."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        # При использовании if not all(TOKENS_TUPLE) не проходится pytest
        logging.critical('Токены отсутствуют')
        raise exceptions.TokensNotAvailable
    logging.debug('Токены найдены')


def send_message(bot: telegram.Bot, message: str):
    """Отправляет сообщение в телеграм о статусе работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except telegram.error.TelegramError as tg_error:
        logging.error(f'Ошибка с функционированием Телеграма: {tg_error}')
    except TypeError:
        logging.error('В функцию send_message'
                      ' передан несоответствующий тип данных')


def get_api_answer(timestamp: int):
    """Отправляет запрос к API Яндекс.Практикума."""
    try:
        request = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp})
        if request.status_code == HTTPStatus.OK:
            request = request.json()
            logging.debug('Запрос к API Яндекса выполнен успешно')
            return request
        # Как вынести его из блока try? except request.status_code != 200?
        # pytest требует четкой проверки на отличие статуса ответа от 200,
        # но чтобы сделать его отдельным блоком надо ведь и переменную request
        # из блока try вынести, как лучше это оформить? вынести переменную в
        # scope функции?
        else:
            logging.error('Сервер Яндекс API недоступен')
            raise exceptions.ServerNotAvailable
    except requests.exceptions.RequestException as error:
        logging.error('Ошибка с запросом к Яндекс API')
        raise Exception(error)


def check_response(response: dict) -> list:
    """Проверяет соответствие ответа API Яндекса ожиданиям."""
    if 'homeworks' not in response:
        logging.error('В response отсутствует ключ homeworks)')
        raise TypeError
    if not isinstance(response, dict):
        logging.error('Response не является словарем')
        raise TypeError
    if not isinstance(response['homeworks'], list):
        logging.error('Отфильтрованный response не является списком')
        raise TypeError

    logging.debug(f'Ответ API проверен! Состав: {response}')
    return response['homeworks']


def parse_status(homework: dict) -> str:
    """Возвращает статус проверки домашней работы."""
    if 'homework_name' not in homework.keys():
        logging.error('В ответе API отсутствует ключ homework_name')
        raise KeyError
    if type(homework['homework_name']) != str:
        logging.error('Название домашней работы не является строкой!')
        raise TypeError
    if homework['status'] not in HOMEWORK_VERDICTS.keys():
        logging.error('Неизвестный статус выполнения ДЗ')
        raise KeyError

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS.get(homework['status'])
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    current_state = ''
    while True:
        try:
            api_request = get_api_answer(timestamp)
            check = check_response(api_request)
            if not check:
                logging.debug('На сервере отсутствует '
                              'информация о домашнем задании')
            else:
                state = parse_status(check[0])
                if state == current_state:
                    logging.critical('Статус проверки не именился, ожидание')
                else:
                    send_message(bot, state)
                    current_state = state
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
