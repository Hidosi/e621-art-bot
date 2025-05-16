from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
import os
from bot import load_config, save_config, download_random_image, load_published_posts, start_scheduler, stop_scheduler_func

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Замените на свой секретный ключ

CONFIG_PATH = 'config.yaml'
LOG_FILE = 'e621_bot.log'

@app.route('/downloaded_images/<path:filename>')
def downloaded_images(filename):
    return send_from_directory('downloaded_images', filename)

@app.route('/', methods=['GET', 'POST'])
def index():
    try:
        config = load_config(CONFIG_PATH)
    except Exception as e:
        flash(f"Ошибка загрузки конфигурации: {e}", "danger")
        config = None

    if 'scheduler_running' not in session:
        session['scheduler_running'] = False
    if 'proxy_enabled_ui' not in session:
        session['proxy_enabled_ui'] = config.get('settings', {}).get('proxy_on', False) if config else False
    if 'page' not in session:
        session['page'] = 0

    tab = request.args.get('tab', 'tags')

    if request.method == 'POST':
        if tab == 'tags':
            tags = request.form.get('tags', '')
            blacklist = request.form.get('blacklist', '')
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]
            blacklist_list = [t.strip() for t in blacklist.split(',') if t.strip()]
            config['e621']['tags'] = tags_list
            config['settings']['blacklist'] = blacklist_list
            save_config(config, CONFIG_PATH)
            flash("Теги и блэклист сохранены!", "success")
            return redirect(url_for('index', tab='tags'))

        elif tab == 'proxy':
            proxy_on = 'proxy_toggle' in request.form
            session['proxy_enabled_ui'] = proxy_on
            if proxy_on:
                proxy_host = request.form.get('proxy_host', '')
                proxy_port = request.form.get('proxy_port', '')
                proxy_login = request.form.get('proxy_login', '')
                proxy_password = request.form.get('proxy_password', '')
                try:
                    proxy_port_int = int(proxy_port)
                except:
                    proxy_port_int = proxy_port
                config['proxy'] = {
                    'host': proxy_host,
                    'port': proxy_port_int,
                    'login': proxy_login,
                    'password': proxy_password
                }
            else:
                config['proxy'] = {}
            config['settings']['proxy_on'] = proxy_on
            save_config(config, CONFIG_PATH)
            flash("Настройки прокси сохранены!", "success")
            return redirect(url_for('index', tab='proxy'))

        elif tab == 'publications':
            if 'publish_now' in request.form:
                flash("Публикация запущена...", "info")
                try:
                    success = download_random_image(config)
                    if success:
                        flash("Публикация выполнена!", "success")
                    else:
                        flash("Публикация не удалась.", "danger")
                except Exception as e:
                    flash(f"Ошибка при публикации: {e}", "danger")
                return redirect(url_for('index', tab='publications'))

            elif 'start_scheduler' in request.form:
                interval_val = config['settings'].get('publish_interval_value', 2)
                interval_unit = config['settings'].get('publish_interval_unit', 'minutes')
                seconds = interval_val * 60 if interval_unit == 'minutes' else interval_val * 3600
                start_scheduler(config, seconds)
                session['scheduler_running'] = True
                flash(f"Планировщик запущен с интервалом {interval_val} {interval_unit}", "success")
                return redirect(url_for('index', tab='publications'))

            elif 'stop_scheduler' in request.form:
                stop_scheduler_func()
                session['scheduler_running'] = False
                flash("Планировщик остановлен", "warning")
                return redirect(url_for('index', tab='publications'))

        elif tab == 'logs':
            if 'clear_logs' in request.form:
                try:
                    open(LOG_FILE, 'w', encoding='utf-8').close()
                    flash("Логи очищены", "success")
                except Exception as e:
                    flash(f"Ошибка при очистке логов: {e}", "danger")
                return redirect(url_for('index', tab='logs'))

        elif tab == 'credentials':
            username = request.form.get('username', '')
            api_key = request.form.get('api_key', '')
            bot_token = request.form.get('bot_token', '')
            chat_id = request.form.get('chat_id', '')
            interval_val = int(request.form.get('interval_val', 2))
            interval_unit = request.form.get('interval_unit', 'minutes')

            config['e621']['username'] = username
            config['e621']['api_key'] = api_key
            config['telegram']['bot_token'] = bot_token
            config['telegram']['chat_id'] = chat_id
            config['settings']['publish_interval_value'] = interval_val
            config['settings']['publish_interval_unit'] = interval_unit
            save_config(config, CONFIG_PATH)
            flash("Учетные данные и интервал публикации сохранены!", "success")
            return redirect(url_for('index', tab='credentials'))

        elif tab == 'published':
            if 'prev_page' in request.form:
                if session['page'] > 0:
                    session['page'] -= 1
                return redirect(url_for('index', tab='published'))
            elif 'next_page' in request.form:
                posts = load_published_posts()
                posts_per_page = 6
                total_pages = (len(posts) - 1) // posts_per_page + 1
                if session['page'] < total_pages - 1:
                    session['page'] += 1
                return redirect(url_for('index', tab='published'))

    published_posts = load_published_posts()
    posts_per_page = 6
    total_pages = (len(published_posts) - 1) // posts_per_page + 1
    page = session.get('page', 0)
    start_idx = page * posts_per_page
    end_idx = start_idx + posts_per_page
    page_posts = published_posts[start_idx:end_idx]

    logs = ''
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = f.read()

    return render_template('index.html',
                           config=config,
                           tab=tab,
                           proxy_enabled=session['proxy_enabled_ui'],
                           scheduler_running=session['scheduler_running'],
                           logs=logs,
                           published_posts=page_posts,
                           page=page,
                           total_pages=total_pages)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)