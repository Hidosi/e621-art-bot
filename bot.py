import requests
import os
import time
import random
import yaml
import sys
import codecs
import logging
import json
import subprocess
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
from PIL import Image
from datetime import datetime
import threading

# Принудительная настройка utf-8 для вывода
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)

LOG_FILE = 'e621_bot.log'
SENT_POSTS_FILE = 'sent_posts.json'
PUBLISHED_POSTS_FILE = 'published_posts.json'
CONFIG_PATH = 'config.yaml'

# Настройка логгера
def setup_logger(log_level=logging.INFO):
    logger = logging.getLogger('e621_bot')
    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
    if logger.hasHandlers():
        logger.handlers.clear()
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger

logger = setup_logger()

# Загрузка конфигурации из YAML
def load_config(config_path=CONFIG_PATH):
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        raise

# Сохранение конфигурации в YAML
def save_config(config, config_path=CONFIG_PATH):
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)
        logger.info("Конфигурация сохранена")
    except Exception as e:
        logger.error(f"Ошибка сохранения конфигурации: {e}")

# Загрузка списка уже отправленных постов
def load_sent_posts():
    if os.path.exists(SENT_POSTS_FILE):
        try:
            with open(SENT_POSTS_FILE, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"Ошибка загрузки списка отправленных постов: {e}")
            return set()
    return set()

# Сохранение списка отправленных постов
def save_sent_posts(sent_posts):
    try:
        with open(SENT_POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(sent_posts), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения списка отправленных постов: {e}")

# Загрузка опубликованных постов с подробностями
def load_published_posts():
    if os.path.exists(PUBLISHED_POSTS_FILE):
        try:
            with open(PUBLISHED_POSTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки опубликованных постов: {e}")
            return []
    return []

# Сохранение опубликованного поста с деталями
def save_published_post(post_data):
    posts = load_published_posts()
    posts.append(post_data)
    try:
        with open(PUBLISHED_POSTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения опубликованного поста: {e}")

# Получение случайной подписи из файла captions.txt
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

# Сжатие изображения для Telegram
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

# Отправка фото в Telegram
def send_photo_to_telegram(file_path, caption=None, config=None):
    if config is None:
        logger.error("Конфигурация не передана в send_photo_to_telegram")
        return False
    TELEGRAM_BOT_TOKEN = config['telegram']['bot_token']
    TELEGRAM_CHAT_ID = config['telegram']['chat_id']
    proxy_on = config['settings'].get('proxy_on', False)
    proxies = None
    if proxy_on:
        PROXY_HOST = config['proxy']['host']
        PROXY_PORT = config['proxy']['port']
        PROXY_LOGIN = config['proxy']['login']
        PROXY_PASSW = config['proxy']['password']
        proxies = {
            'http': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}'
        }
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
    try:
        compressed_path = compress_image(file_path)
        with open(compressed_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': TELEGRAM_CHAT_ID}
            if caption:
                data['caption'] = caption
                data['parse_mode'] = 'Markdown'
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

# Конвертация webm в mp4 с помощью ffmpeg
def convert_webm_to_mp4(input_path):
    output_path = input_path.rsplit('.', 1)[0] + '.mp4'
    try:
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264', '-preset', 'fast',
            '-c:a', 'aac', '-strict', 'experimental',
            output_path
        ], check=True)
        return output_path
    except Exception as e:
        logger.error(f"Ошибка конвертации webm в mp4: {e}")
        return None

# Отправка видео в Telegram с конвертацией webm в mp4
def send_video_to_telegram(file_path, caption=None, config=None):
    if config is None:
        logger.error("Конфигурация не передана в send_video_to_telegram")
        return False

    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.webm':
        mp4_path = convert_webm_to_mp4(file_path)
        if mp4_path:
            file_path = mp4_path
        else:
            logger.error("Не удалось конвертировать webm в mp4, отправляем оригинал")

    TELEGRAM_BOT_TOKEN = config['telegram']['bot_token']
    TELEGRAM_CHAT_ID = config['telegram']['chat_id']
    proxy_on = config['settings'].get('proxy_on', False)
    proxies = None
    if proxy_on:
        PROXY_HOST = config['proxy']['host']
        PROXY_PORT = config['proxy']['port']
        PROXY_LOGIN = config['proxy']['login']
        PROXY_PASSW = config['proxy']['password']
        proxies = {
            'http': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}'
        }
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo'
    try:
        with open(file_path, 'rb') as video:
            files = {'video': video}
            data = {'chat_id': TELEGRAM_CHAT_ID}
            if caption:
                data['caption'] = caption
                data['parse_mode'] = 'Markdown'
            logger.debug(f"Отправка видео в Telegram: {file_path} с caption: {caption}")
            response = requests.post(url, files=files, data=data, proxies=proxies, timeout=60)
        logger.debug(f"Ответ Telegram (видео): {response.status_code} {response.text}")
        if response.status_code == 200:
            logger.info("Видео успешно отправлено в Телеграм")
            # Если был создан временный mp4, можно удалить его после отправки
            if ext == '.webm' and mp4_path and os.path.exists(mp4_path):
                try:
                    os.remove(mp4_path)
                    logger.debug(f"Удалён временный файл конвертированного видео: {mp4_path}")
                except Exception as e:
                    logger.error(f"Ошибка удаления временного файла: {e}")
            return True
        else:
            logger.error(f"Ошибка при отправке видео: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Критическая ошибка отправки видео: {e}")
        return False

# Отправка медиа (фото или видео) в Telegram
def send_media_to_telegram(file_path, caption=None, config=None):
    video_extensions = ('.mp4', '.mov', '.mkv', '.avi')  # убрал .webm из видео
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.webm')  # добавил .webm сюда, чтобы обрабатывать через send_video_to_telegram с конвертацией

    ext = os.path.splitext(file_path)[1].lower()
    if ext in video_extensions or ext == '.webm':
        return send_video_to_telegram(file_path, caption, config)
    elif ext in image_extensions:
        return send_photo_to_telegram(file_path, caption, config)
    else:
        logger.error(f"Неизвестный тип файла для отправки: {file_path}")
        return False

# Загрузка списка отправленных постов в память
sent_posts = load_sent_posts()

# Функция скачивания случайного изображения и отправки в Telegram
def download_random_image(config=None):
    if config is None:
        logger.error("Конфигурация не передана в download_random_image")
        return False
    url = 'https://e621.net/posts.json'
    tags = config['e621']['tags']
    tags_count = config['settings'].get('tags_count', len(tags))
    blacklist = config['settings'].get('blacklist', [])

    # Убираем None и пустые из blacklist
    clean_blacklist = [tag for tag in blacklist if tag and str(tag).lower() != 'none']

    attempts = 0
    max_attempts = 3
    USERNAME = config['e621']['username']
    API_KEY = config['e621']['api_key']

    proxy_on = config['settings'].get('proxy_on', False)
    proxies = None
    if proxy_on:
        PROXY_HOST = config['proxy']['host']
        PROXY_PORT = config['proxy']['port']
        PROXY_LOGIN = config['proxy']['login']
        PROXY_PASSW = config['proxy']['password']
        proxies = {
            'http': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}',
            'https': f'socks5h://{PROXY_LOGIN}:{PROXY_PASSW}@{PROXY_HOST}:{PROXY_PORT}'
        }

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

            artists_line = f"👨‍🎨 Художник: {' '.join(f'#{tag}' for tag in artists)}" if artists else ""
            characters_line = f"🎭 Персонаж: {' '.join(f'#{tag}' for tag in characters)}" if characters else ""

            caption_parts = [
                caption_text,
                artists_line,
                characters_line,
                f"----",
                f"[Открыть оригинал]({post_url})"
            ]

            caption = "\n".join(filter(None, caption_parts))

            if send_media_to_telegram(filename, caption=caption, config=config):
                sent_posts.add(post_id)
                sent_posts.add(post_md5)
                save_sent_posts(sent_posts)

                # Сохраняем подробности публикации для просмотра в UI
                post_data = {
                    "id": post_id,
                    "image_url": image_url,
                    "local_path": filename,
                    "caption": caption,
                    "post_url": post_url
                }
                save_published_post(post_data)

                return True
            else:
                logger.error("Не удалось отправить медиа, пробуем другой пост...")

        except RequestException as e:
            logger.error(f"Ошибка при загрузке: {e}")
            break
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            break

    logger.warning("Не удалось найти уникальное изображение после нескольких попыток, пропускаем публикацию")
    return False

# Управление планировщиком
stop_scheduler = False
scheduler_thread = None

def scheduler_worker(config, interval_seconds):
    global stop_scheduler
    while not stop_scheduler:
        try:
            download_random_image(config)
        except Exception as e:
            logger.error(f"Ошибка в планировщике: {e}")
        time.sleep(interval_seconds)

def start_scheduler(config, interval_seconds=120):
    global scheduler_thread, stop_scheduler
    if scheduler_thread is None or not scheduler_thread.is_alive():
        stop_scheduler = False
        scheduler_thread = threading.Thread(target=scheduler_worker, args=(config, interval_seconds), daemon=True)
        scheduler_thread.start()
        logger.info(f"Планировщик запущен с интервалом {interval_seconds} секунд")

def stop_scheduler_func():
    global stop_scheduler
    stop_scheduler = True
    logger.info("Планировщик остановлен")

# Если запускаем напрямую, стартуем планировщик с дефолтным интервалом
if __name__ == '__main__':
    try:
        config = load_config()
        start_scheduler(config)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Работа приложения завершена пользователем")
        stop_scheduler_func()
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")