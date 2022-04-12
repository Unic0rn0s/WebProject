from flask import Flask, render_template, redirect
from data import db_session
from forms.user import RegisterForm
from data.users import User
from google_drive_auth import google_drive_auth

app = Flask('Sus')
app.config['SECRET_KEY'] = 'sus))'


@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', title='Home')


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form, message="Пароли не совпадают")
        db_sess = db_session.create_session()

        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form, message="Такой пользователь уже есть")

        user = User(name=form.name.data, email=form.email.data)
        user.set_password(form.password.data)

        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')

    return render_template('register.html', title='Регистрация', form=form)


@app.route('/login')
def login():
    return render_template('login.html', title='Login')


@app.route('/google_drive_auth')
def google_auth():
    google_drive_auth()
    return redirect('http://localhost:5000/')


db_session.global_init('db/sqlite.db')

app.run(host='localhost', port=5000)
