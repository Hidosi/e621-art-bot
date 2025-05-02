import requests
import os
import time
import schedule
import random
import yaml
import sys
import codecs
import logging
import argparse
import json
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from PIL import Image
from datetime import datetime

# Принудительная настройка utf-8
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

def setup_logger(log_level):
    level_map = {0: logging.DEBUG, 1: logging.INFO, 2: logging.ERROR}
    level = level_map.get(log_level, logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
    if logger.hasHandlers():
        logger.handlers.clear()
    file_handler = logging.FileHandler('e621_bot.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

parser = argparse.ArgumentParser(description='e621 Telegram Bot')
parser.add_argument('--loglevel', type=int, choices=[0,1,2], default=1,
                    help='Уровень логирования: 0 - подробный, 1 - стандартный (по умолчанию), 2 - только ошибки')
args = parser.parse_args()

logger = setup_logger(args.loglevel)

SENT_POSTS_FILE = 'sent_posts.json'

def load_sent_posts():
    if os.path.exists(SENT_POSTS_FILE):
        try:
            with open(SENT_POSTS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"Ошибка загрузки списка отправленных постов: {e}")
            return set()
    return set()

def save_sent_posts(sent_posts):
    try:
        with open(SENT_POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения списка отправленных постов: {e}")

def load_config(config_path='config.yaml'):
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        raise

def get_random_caption(filename='captions.txt'):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        caption = random.choice(lines) if lines else ''
        logger.debug(f"Выбран caption: {caption}")
        return caption
    except Exception as e:
        logger.error(f"Ошибка чтения caption из файла: {e}")
        return ''

CONFIG = None
try:
    CONFIG = load_config()
except Exception:
    logger.critical("Не удалось загрузить конфигурацию. Завершение работы.")
    exit(1)

# Настройка прокси в зависимости от proxy_on
proxy_on = CONFIG['settings'].get('proxy_on', False)

if proxy_on:
    PROXY_HOST = CONFIG['proxy']['host']
    PROXY_PORT = CONFIG['proxy']['port']
    PROXY_LOGIN = CONFIG['proxy']['login']
    PROXY_PASSW = CONFIG['proxy']['password']

    proxies = {
        'http': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}',
        'https': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}'
    }
    logger.info("Прокси включён")
else:
    proxies = None
    logger.info("Прокси выключен, работаем напрямую")

USERNAME = CONFIG['e621']['username']
API_KEY = CONFIG['e621']['api_key']

TELEGRAM_BOT_TOKEN = CONFIG['telegram']['bot_token']
TELEGRAM_CHAT_ID = CONFIG['telegram']['chat_id']

def compress_image(input_path, max_size=(1920, 1080), quality=85):
    try:
        with Image.open(input_path) as img:
            img.thumbnail(max_size, Image.LANCZOS)
            compressed_path = input_path.replace('.', '_compressed.')
            img.save(compressed_path, optimize=True, quality=quality)
        logger.debug(f"Изображение сжато: {input_path} -> {compressed_path}")
        return compressed_path
    except Exception as e:
        logger.error(f"Ошибка сжатия изображения: {e}")
        return input_path

def send_photo_to_telegram(file_path, caption=None):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    try:
        compressed_path = compress_image(file_path)
        with open(compressed_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': TELEGRAM_CHAT_ID}
            if caption:
                data['caption'] = caption
            logger.debug(f"Отправка фото в Telegram: {compressed_path} с caption: {caption}")
            response = requests.post(url, files=files, data=data, proxies=proxies, timeout=30)
        if compressed_path != file_path:
            os.remove(compressed_path)
            logger.debug(f"Удалён временный сжатый файл: {compressed_path}")
        logger.debug(f"Ответ Telegram: {response.status_code} {response.text}")
        if response.status_code == 200:
            logger.info("Фото успешно отправлено в Телеграм")
            return True
        else:
            logger.error(f"Ошибка при отправке фото: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Критическая ошибка отправки: {e}")
        return False

def send_video_to_telegram(file_path, caption=None):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo'
    try:
        with open(file_path, 'rb') as video:
            files = {'video': video}
            data = {'chat_id': TELEGRAM_CHAT_ID}
            if caption:
                data['caption'] = caption
            logger.debug(f"Отправка видео в Telegram: {file_path} с caption: {caption}")
            response = requests.post(url, files=files, data=data, proxies=proxies, timeout=60)
        logger.debug(f"Ответ Telegram (видео): {response.status_code} {response.text}")
        if response.status_code == 200:
            logger.info("Видео успешно отправлено в Телеграм")
            return True
        else:
            logger.error(f"Ошибка при отправке видео: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Критическая ошибка отправки видео: {e}")
        return False

def send_media_to_telegram(file_path, caption=None):
    video_extensions = ('.mp4', '.mov', '.webm', '.mkv', '.avi')
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    ext = os.path.splitext(file_path)[1].lower()
    if ext in video_extensions:
        return send_video_to_telegram(file_path, caption)
    elif ext in image_extensions:
        return send_photo_to_telegram(file_path, caption)
    else:
        logger.error(f"Неизвестный тип файла для отправки: {file_path}")
        return False

sent_posts = load_sent_posts()

def download_random_image(max_attempts=3):
    url = 'https://e621.net/posts.json'
    tags = CONFIG['e621']['tags']
    tags_count = CONFIG['settings']['tags_count']
    blacklist = CONFIG['settings'].get('blacklist', [])

    # Убираем None и пустые из blacklist
    clean_blacklist = [tag for tag in blacklist if tag and str(tag).lower() != 'none']

    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        try:
            selected_tags = ' '.join(random.sample(tags, k=min(tags_count, len(tags))))
            blacklist_tags = ' '.join(f'-{tag}' for tag in clean_blacklist)
            tags_query = f'order:random {selected_tags} {blacklist_tags}'

            headers = {'User-Agent': f'ImageDownloader/1.0 (by {USERNAME} on e621)'}
            auth = HTTPBasicAuth(USERNAME, API_KEY)

            logger.info(f"Запрос к API e621 с тегами: {tags_query}")

            response = requests.get(url, headers=headers, params={'tags': tags_query, 'limit': 1},
                                    proxies=proxies, timeout=30, auth=auth)
            logger.debug(f"Ответ сервера e621: {response.status_code} {response.text[:1000]}")

            response.raise_for_status()
            data = response.json()

            if not data.get('posts'):
                logger.warning("Не найдено изображений")
                continue

            post = data['posts'][0]
            post_id = post['id']
            post_md5 = post['file']['md5']

            if post_id in sent_posts or post_md5 in sent_posts:
                logger.info(f"Найден дубликат поста с ID {post_id} (попытка {attempts}/{max_attempts}), пропускаем и ищем новый.")
                continue

            image_url = post['file']['url']
            if not image_url:
                logger.warning("У поста нет доступного изображения")
                continue

            post_url = f"https://e621.net/posts/{post_id}"
            logger.info(f"Обрабатываем пост: {post_url}")

            date_folder = datetime.now().strftime("%Y-%m-%d")
            os.makedirs(f'downloaded_images/{date_folder}', exist_ok=True)

            file_extension = image_url.split('.')[-1].split('?')[0]
            timestamp = int(time.time())
            filename = f'downloaded_images/{date_folder}/e621_image_{timestamp}.{file_extension}'

            logger.info(f"Скачиваем изображение: {image_url}")

            img_response = requests.get(image_url, headers=headers, proxies=proxies, timeout=30)
            logger.debug(f"Ответ сервера с изображением: {img_response.status_code}")

            img_response.raise_for_status()

            with open(filename, 'wb') as f:
                f.write(img_response.content)

            logger.info(f"Изображение сохранено: {filename}")

            artists = post['tags'].get('artist', [])
            characters = post['tags'].get('character', [])

            caption_text = get_random_caption('captions.txt')

            artists_line = f"Художник: {' '.join(f'#{tag}' for tag in artists)}" if artists else ""
            characters_line = f"Персонаж: {' '.join(f'#{tag}' for tag in characters)}" if characters else ""

            post_url = f"\nhttps://e621.net/posts/{post_id}"

            caption_parts = [caption_text]
            if artists_line:
                caption_parts.append(artists_line)
            if characters_line:
                caption_parts.append(characters_line)
            caption_parts.append(post_url)

            caption = "\n".join(caption_parts)

            if send_media_to_telegram(filename, caption=caption):
                sent_posts.add(post_id)
                sent_posts.add(post_md5)
                save_sent_posts(sent_posts)
                return
            else:
                logger.error("Не удалось отправить медиа, пробуем другой пост...")

        except RequestException as e:
            logger.error(f"Ошибка при загрузке: {e}")
            break
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            break

    logger.warning("Не удалось найти уникальное изображение после нескольких попыток, пропускаем публикацию")

def start_scheduling():
    logger.info("Запуск планировщика")
    schedule.every(2).minutes.do(download_random_image)
    download_random_image()
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    try:
        start_scheduling()
    except KeyboardInterrupt:
        logger.info("Работа приложения завершена пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")