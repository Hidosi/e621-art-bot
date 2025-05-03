import streamlit as st
import yaml
import threading
import time
from bot import download_random_image, load_config, save_config

CONFIG_PATH = 'config.yaml'
LOG_FILE = 'e621_bot.log'

# Глобальные переменные для управления планировщиком
stop_scheduler = False
scheduler_thread = None

def scheduler_worker(config, interval_seconds):
    global stop_scheduler
    while not stop_scheduler:
        try:
            download_random_image(config)
        except Exception as e:
            st.error(f"Ошибка в планировщике: {e}")
        time.sleep(interval_seconds)

def start_scheduler_with_interval(config, interval_seconds):
    global scheduler_thread, stop_scheduler
    if scheduler_thread is None or not scheduler_thread.is_alive():
        stop_scheduler = False
        scheduler_thread = threading.Thread(target=scheduler_worker, args=(config, interval_seconds), daemon=True)
        scheduler_thread.start()

def stop_scheduler_func_wrapper():
    global stop_scheduler
    stop_scheduler = True

# Инициализация состояния
if 'scheduler_running' not in st.session_state:
    st.session_state['scheduler_running'] = False
if 'proxy_enabled_ui' not in st.session_state:
    try:
        config_cache = load_config(CONFIG_PATH)
        st.session_state['proxy_enabled_ui'] = config_cache.get('settings', {}).get('proxy_on', False)
    except Exception:
        st.session_state['proxy_enabled_ui'] = False

st.set_page_config(page_title="e621 Dashboard", page_icon="📡", layout="wide")

# Стили
st.markdown("""
    <style>
        .big-title { font-size: 40px; font-weight: bold; color: #4CAF50; }
        .section-title { font-size: 24px; margin-top: 20px; color: #2196F3; display: flex; justify-content: space-between; align-items: center; }
        .info-box { background-color: #f0f0f5; padding: 15px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">📡 e621 Telegram Dashboard</div>', unsafe_allow_html=True)

# Загружаем конфиг
try:
    config = load_config(CONFIG_PATH)
except Exception as e:
    st.error(f"Ошибка загрузки конфигурации: {e}")
    st.stop()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📌 Теги",
    "🌐 Прокси",
    "📤 Публикации",
    "📄 Логи",
    "⚙️ Учетные данные"
])

# --- Теги ---
with tab1:
    st.markdown('<div class="section-title">📌 Настройка тегов</div>', unsafe_allow_html=True)
    tags = st.text_area("Теги (через запятую)", value=", ".join(config['e621']['tags']))
    tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

    blacklist = st.text_area("Блэклист (через запятую)", value=", ".join(config['settings'].get('blacklist', [])))
    blacklist_list = [tag.strip() for tag in blacklist.split(",") if tag.strip()]

    if st.button("💾 Сохранить теги и блэклист"):
        config['e621']['tags'] = tags_list
        config['settings']['blacklist'] = blacklist_list
        save_config(config, CONFIG_PATH)
        st.success("Теги и блэклист сохранены!")

# --- Прокси ---
with tab2:
    col1, col2 = st.columns([6, 1])
    with col1:
        st.markdown('<div class="section-title">🌐 Настройки прокси</div>', unsafe_allow_html=True)
    with col2:
        proxy_toggle = st.checkbox("Включить прокси", value=st.session_state['proxy_enabled_ui'], key="proxy_toggle")
        st.session_state['proxy_enabled_ui'] = proxy_toggle

    proxy = config.get('proxy', {})
    settings = config.get('settings', {})

    if st.session_state['proxy_enabled_ui']:
        col1, col2 = st.columns(2)
        with col1:
            proxy_host = st.text_input("Proxy Host", value=proxy.get('host', ''))
            proxy_login = st.text_input("Proxy Login", value=proxy.get('login', ''))
        with col2:
            proxy_port = st.text_input("Proxy Port", value=str(proxy.get('port', '')))
            proxy_password = st.text_input("Proxy Password", value=proxy.get('password', ''), type="password")
    else:
        proxy_host = proxy_login = proxy_port = proxy_password = None

    if st.button("💾 Сохранить настройки прокси"):
        if st.session_state['proxy_enabled_ui']:
            config['proxy'] = {
                'host': proxy_host or '',
                'port': int(proxy_port) if proxy_port and proxy_port.isdigit() else proxy_port or '',
                'login': proxy_login or '',
                'password': proxy_password or ''
            }
        else:
            config['proxy'] = {}
        config['settings']['proxy_on'] = st.session_state['proxy_enabled_ui']
        save_config(config, CONFIG_PATH)
        st.success("Настройки прокси сохранены!")

# --- Публикации ---
with tab3:
    st.markdown('<div class="section-title">📤 Управление публикациями</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 6])

    with col1:
        if st.button("🚀 Опубликовать сейчас"):
            st.info("Публикация запущена...")
            try:
                success = download_random_image(config)
                if success:
                    st.success("Публикация выполнена!")
                else:
                    st.error("Публикация не удалась.")
            except Exception as e:
                st.error(f"Ошибка при публикации: {e}")

    with col2:
        if not st.session_state.get('scheduler_running', False):
            if st.button("▶️ Запустить планировщик"):
                with st.spinner("Запуск планировщика..."):
                    interval_val = config['settings'].get('publish_interval_value', 2)
                    interval_unit = config['settings'].get('publish_interval_unit', 'minutes')
                    seconds = interval_val * 60 if interval_unit == 'minutes' else interval_val * 3600
                    start_scheduler_with_interval(config, interval_seconds=seconds)
                    st.session_state['scheduler_running'] = True
                st.success(f"Планировщик запущен с интервалом {interval_val} {interval_unit}")
        else:
            if st.button("⏹ Остановить планировщик"):
                with st.spinner("Остановка планировщика..."):
                    stop_scheduler_func_wrapper()
                    st.session_state['scheduler_running'] = False
                st.warning("Планировщик остановлен")

# --- Логи ---
with tab4:
    st.markdown('<div class="section-title">📄 Последние логи</div>', unsafe_allow_html=True)
    if st.checkbox("Показать логи"):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                logs = f.read()
            st.text_area("Логи", value=logs, height=300)
        except Exception as e:
            st.error(f"Не удалось загрузить логи: {e}")

    if st.button("🧹 Очистить логи"):
        try:
            open(LOG_FILE, 'w', encoding='utf-8').close()
            st.success("Логи очищены")
        except Exception as e:
            st.error(f"Ошибка при очистке логов: {e}")

# --- Учетные данные ---
with tab5:
    st.markdown('<div class="section-title">⚙️ Настройка учетных данных и интервала публикации</div>', unsafe_allow_html=True)
    username = st.text_input("e621 Username", value=config['e621'].get('username', ''))
    api_key = st.text_input("e621 API Key", value=config['e621'].get('api_key', ''))
    bot_token = st.text_input("Telegram Bot Token", value=config['telegram'].get('bot_token', ''))
    chat_id = st.text_input("Telegram Chat ID", value=str(config['telegram'].get('chat_id', '')))

    interval_val = st.number_input("Интервал публикации", min_value=1, max_value=1440,
                                   value=config['settings'].get('publish_interval_value', 2), step=1)
    interval_unit = st.selectbox("Единицы интервала", options=['minutes', 'hours'],
                                 index=0 if config['settings'].get('publish_interval_unit', 'minutes') == 'minutes' else 1)

    if st.button("💾 Сохранить учетные данные и интервал"):
        config['e621']['username'] = username
        config['e621']['api_key'] = api_key
        config['telegram']['bot_token'] = bot_token
        config['telegram']['chat_id'] = chat_id
        config['settings']['publish_interval_value'] = interval_val
        config['settings']['publish_interval_unit'] = interval_unit
        save_config(config, CONFIG_PATH)
        st.success("Учетные данные и интервал публикации сохранены!")