from requests import post
from flask import Flask, render_template, redirect, request
from urllib.parse import urlencode
from data import db_session
from forms.user import RegisterForm, LoginForm
from data.users import User
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import yadisk
from yadisk_config import CLIENT_ID, CLIEND_SECRET


# Настройки приложения
app = Flask('Sus')
app.config['SECRET_KEY'] = 'sus))'

# Работа с авторизацией
login_manager = LoginManager()
login_manager.init_app(app)

# Яндекс.Диск
client_id = CLIENT_ID
client_secret = CLIEND_SECRET
baseurl = 'https://oauth.yandex.ru/'


# Загрузка пользователя из БД
@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


# Базовая страница
@app.route('/')
def root():
    return render_template('base.html', title='Amogus')


# Домашняя страница
@app.route('/home')
@login_required
def home():
    # Проверка токена Яндекс.Диска
    user = load_user(current_user.get_id())
    current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
    if current_user.yandex_disk.check_token():
        print(yandex_files())
        return render_template('home.html', title='Главная', chapters=yandex_files())

    return render_template('home.html', title='Главная', data='Токен не действителен')


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
            return redirect('/home')
        return render_template('login.html', message='Неправильный логин или пароль',
                               form=form, error=None)

    return render_template('login.html', title='Авторизация', form=form)


# Обработка выхода пользователя
@app.route('/logout')
@login_required
def logout():
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
        return redirect('/home')

    # Иначе отправляем пользователя на страницу авторизации
    return redirect(baseurl + "authorize?response_type=code&client_id={}".format(client_id))


# Получение папок и файлов из Яндекс.Диска
def yandex_files():
    result = list()
    for i in current_user.yandex_disk.listdir('/'):
        result.append((i.name, [j.name for j in current_user.yandex_disk.listdir(i.path)]))
    return result


# Обработчик ошибки авторизации
@app.errorhandler(401)
def not_auth(e):
    return redirect('/login')


# Добавление раздела
@app.route('/add_chapter', methods=['POST'])
@login_required
def add_chapter():
    name = request.form['add']
    user = load_user(current_user.get_id())
    current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
    try:
        current_user.yandex_disk.mkdir(f'/{name}')
    except Exception:
        return render_template('home.html', title='Главная',
                               chapters=yandex_files(), error='Указан неверный раздел')
    return redirect('/home')


# Удаление раздела
@app.route('/delete_chapter', methods=['POST'])
@login_required
def delete_chapter():
    name = request.form['del']
    user = load_user(current_user.get_id())
    current_user.yandex_disk = yadisk.YaDisk(token=user.yadisk_token)
    try:
        current_user.yandex_disk.remove(f'/{name}')
    except Exception:
        return render_template('home.html', title='Главная',
                               chapters=yandex_files(), error='Указан неверный раздел')

    return redirect('/home')


# Инициализация БД
db_session.global_init('db/sqlite.db')

# Запуск приложения
if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)
