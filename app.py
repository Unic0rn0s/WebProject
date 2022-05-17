from requests import post
from flask import Flask, render_template, redirect, request
from urllib.parse import urlencode
from data import db_session
from forms.user import RegisterForm, LoginForm
from data.users import User
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import yadisk
from yadisk_config import CLIENT_ID, CLIENT_SECRET
from flask_restful import Api
from api.resources import UserResource, UsersListResource
from waitress import serve
import logging


# Создание приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sus))'

# API
api = Api(app)
api.add_resource(UsersListResource, '/users')
api.add_resource(UserResource, '/users/<int:user_id>')

# Работа с авторизацией
login_manager = LoginManager()
login_manager.init_app(app)

# Яндекс.Диск
client_id = CLIENT_ID
client_secret = CLIENT_SECRET
baseurl = 'https://oauth.yandex.ru/'

# Логирование
logging.basicConfig(filename='app.log',
                    format='%(asctime)s %(levelname)s %(name)s %(message)s',
                    level=logging.INFO)


# Загрузка пользователя из БД
@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


# Базовая страница
@app.route('/')
def root():
    return render_template('amogus.html', title='Amogus')


# Домашняя страница
@app.route('/home')
@login_required
def home():
    # Проверка токена Яндекс.Диска
    user = load_user(current_user.get_id())
    current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
    # Если токен действителен:
    if current_user.yandex_disk.check_token():
        return render_template('home.html', title='Главная', chapters=yandex_files())

    return invalid_token()


# Страница регистрации
@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        # Если пользователь нажал войти, проверяем пароли и уникальность почты
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form, message='Пароли не совпадают')
        db_sess = db_session.create_session()

        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form, message='Такой пользователь уже есть')

        user = User(name=form.name.data, email=form.email.data)
        user.set_password(form.password.data)

        db_sess.add(user)
        db_sess.commit()

        logging.info(f'New user {user.name} register')

        return redirect('/login')

    return render_template('register.html', title='Регистрация', form=form)


# Страница авторизации
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        # Сверяем введённые данные с БД
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)

            logging.info(f'User {user.name} logged')

            return redirect('/home')
        return render_template('login.html', message='Неправильный логин или пароль',
                               form=form, error=None)

    return render_template('login.html', title='Авторизация', form=form)


# Обработка выхода пользователя
@app.route('/logout')
@login_required
def logout():
    user = load_user(current_user.get_id())
    logging.info(f'User {user.name} logout')
    logout_user()
    return redirect('/')


# Получение токена пользователя для Яндекс.Диска
@app.route('/yadisk_auth')
@login_required
def yadisk_auth():

    # Если пользователь подтвердил разрешение, получаем код
    if request.args.get('code', False):
        data = {
            'grant_type': 'authorization_code',
            'code': request.args.get('code'),
            'client_id': client_id,
            'client_secret': client_secret
        }
        data = urlencode(data)
        # С помощью кода подтверждения получаем токен в json ответе
        data = post(baseurl + "token", data).json()
        token = data['access_token']

        # Обновляем токен в БД
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.id == current_user.get_id()).first()
        user.yadisk_token = token

        db_sess.add(user)
        db_sess.commit()

        logging.info(f'User {user.name} got token')
        return redirect('/home')

    # Иначе отправляем пользователя на страницу авторизации
    return redirect(baseurl + "authorize?response_type=code&client_id={}".format(client_id))


# Получение папок и файлов из Яндекс.Диска
def yandex_files():
    result = list()
    for i in current_user.yandex_disk.listdir('/'):
        # Пока записывается путь, файл уже может быть удалён
        try:
            files = list()
            for j in current_user.yandex_disk.listdir(i.path):
                files.append(j.name)
            result.append((i.name, files))
        # Продолжаем работу, еслы такой был найден
        except Exception:
            continue

    return result


# Добавление раздела
@app.route('/add_chapter', methods=['POST'])
def add_chapter():
    try:
        name = request.form['add']
        user = load_user(current_user.get_id())
        current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
        current_user.yandex_disk.mkdir(f'/{name}')
    except Exception:
        if current_user.yandex_disk.check_token():
            return render_template('home.html', title='Главная',
                                   chapters=yandex_files(), error='Указан неверный раздел')
        return invalid_token()

    return redirect('/home')


# Удаление раздела/файла
@app.route('/delete_path', methods=['POST'])
def delete_path():
    try:
        name = request.form['del']
        user = load_user(current_user.get_id())
        current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
        current_user.yandex_disk.remove(name, permanently=True)
    except Exception:
        if current_user.yandex_disk.check_token():
            return render_template('home.html', title='Главная',
                                   chapters=yandex_files(), error='Неверный путь')
        return invalid_token()

    return redirect('/home')


# Загрузка файла на Яндекс.Диск
@app.route('/add_file', methods=['POST'])
def add_file():
    try:
        # Для загрузки нужно содержимое файла и путь на Яндекс.Диске
        name = request.form['add_file']
        file = request.files['file']
        user = load_user(current_user.get_id())
        current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
        # Путь на диске - название файла
        current_user.yandex_disk.upload(file, f'/{name}/{file.filename}')
    except Exception:
        if current_user.yandex_disk.check_token():
            return render_template('home.html', title='Главная',
                                   chapters=yandex_files(), error='Неверный файл или раздел')
        return invalid_token()
    return redirect('/home')


# Открытие файла в Яндекс.Диске
@app.route('/open_path', methods=['POST'])
def open_path():
    try:
        user = load_user(current_user.get_id())
        current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
        path = request.form['open_path']
        if path and current_user.yandex_disk.exists(path):
            # Отправляем пользователя по сгенерированному url
            return redirect(url_file(path))
        return render_template('home.html', title='Главная',
                               chapters=yandex_files(), error='Неверный путь')
    except Exception:
        return invalid_token()


# Получение ссылки на скачивание файла
@app.route('/download_link', methods=['POST'])
def download_link():
    try:
        path = request.form['download_link']
        user = load_user(current_user.get_id())
        current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
        if path and current_user.yandex_disk.exists(path):
            # Для генерации ссылки нужен только путь на Яндекс.Диске
            # Ссылка действительна для всех
            link = current_user.yandex_disk.get_download_link(path)
            return render_template('home.html', title='Главная',
                                   chapters=yandex_files(), success=link)
        return render_template('home.html', title='Главная',
                               chapters=yandex_files(), error='Неверный путь')
    except Exception:
        return invalid_token()


# Сообщаем, если токен не работает
def invalid_token():
    # Передаём пустой список в параметр разделов, чтобы цикл в шаблоне не запускался
    return render_template('home.html', title='Главная',
                           chapters=[], error='Токен не действителен')


# Получение url для файла на Яндекс.Диске
def url_file(path):
    # Приводим путь к файлу в нужный формат
    directory = path.split('/')[0]
    path = path.replace('/', '%2F')
    return f'https://disk.yandex.ru/client/disk/{directory}' \
           f'?idApp=client&dialog=slider&idDialog=%2Fdisk{path}'


# Отзыв токена для Яндекс.Диска
@app.route('/del_token')
def del_token():
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(User.id == current_user.get_id()).first()
    user.yadisk_token = None

    db_sess.add(user)
    db_sess.commit()

    logging.info(f'User {user.name} deleted the token')
    return redirect('/home')


# Обработчик ошибки авторизации
@app.errorhandler(401)
def not_auth(e):
    return redirect('/login')


# Инициализация БД
db_session.global_init('db/sqlite.db')

# Запуск приложения
if __name__ == '__main__':
    host, port = '0.0.0.0', 5000
    # app.run(host=host, port=port, debug=True)
    logging.info(f'App started, host:{host} port:{port}')
    serve(app, host=host, port=port)
