from flask import Flask, render_template

app = Flask('Sus')
app.config['SECRET_KEY'] = 'sus))'


@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', title='Home')


app.run(host='localhost', port=8080, debug=True)
