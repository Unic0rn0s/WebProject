from requests import post
from flask import Flask, render_template, redirect, request, jsonify
from urllib.parse import urlencode
from data import db_session
from forms.user import RegisterForm, LoginForm
from data.users import User
from flask_login import LoginManager, login_user, login_required, logout_user
import yadisk
from yadisk_config import CLIENT_ID, CLIEND_SECRET


app = Flask('Sus')
app.config['SECRET_KEY'] = 'sus))'

login_manager = LoginManager()
login_manager.init_app(app)

# Яндекс.Диск
client_id = CLIENT_ID
client_secret = CLIEND_SECRET
baseurl = 'https://oauth.yandex.ru/'


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.route('/')
def root():
    return render_template('base.html', title='Amogus')


@app.route('/home/<data>')
def home(data):
    return render_template('home.html', title='Home', data=data)


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
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


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect('/')
        return render_template('login.html', message='Неправильный логин или пароль', form=form)
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/')


@app.route('/yadisk_auth')
def yadisk_auth():
    if request.args.get('code', False):
        data = {
            'grant_type': 'authorization_code',
            'code': request.args.get('code'),
            'client_id': client_id,
            'client_secret': client_secret
        }
        data = urlencode(data)
        data = post(baseurl + "token", data).json()
        print(data['access_token'])
        y = yadisk.YaDisk(token=data['access_token'])
        print(y.check_token())
        print(list(y.listdir("/Images")))
        return data['access_token']
    else:
        return redirect(baseurl + "authorize?response_type=code&client_id={}".format(client_id))


db_session.global_init('db/sqlite.db')

app.run(host='localhost', port=5000, debug=True)
