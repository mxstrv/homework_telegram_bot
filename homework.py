import requests
import os
import telegram
import time
import logging
import sys
import exceptions

from dotenv import load_dotenv
from http import HTTPStatus


load_dotenv()

PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
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

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] - %(message)s',
    level=logging.DEBUG,
)
logging.StreamHandler(stream=sys.stdout)


def check_tokens():
    """Проверяет доступны ли токены в окружении."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.critical('Токены отсутствуют')
        raise exceptions.TokensNotAvailable
    logging.debug('Токены найдены')


def send_message(bot, message):
    """Отправляет сообщение в телеграм о статусе работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение: {message}')
    except Exception as error:
        logging.error(error)


def get_api_answer(timestamp):
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
        else:
            logging.error('Сервер Яндекс API недоступен')
            raise exceptions.ServerNotAvailable
    except requests.exceptions.RequestException as error:
        logging.error('Ошибка с запросом к Яндекс API')
        raise Exception(error)


def check_response(response):
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


def parse_status(homework):
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
