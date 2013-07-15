import os
from flask.ext.login import LoginManager
from flask.ext.openid import OpenID
from config import basedir
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from momentjs import momentjs
from flask_oauth import OAuth

app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)
lm = LoginManager()
lm.setup_app(app)
lm.login_view = 'login'
oid = OpenID(app, os.path.join(basedir, 'tmp'))


app.jinja_env.globals['momentjs'] = momentjs


oauth = OAuth()
facebook = oauth.remote_app('facebook',
    base_url='https://graph.facebook.com/',
    request_token_url=None,
    access_token_url='/oauth/access_token',
    authorize_url='https://www.facebook.com/dialog/oauth',
    consumer_key='F180236948816069',
    consumer_secret='becbcdbb934c58dae6e4305798d89b00',
    request_token_params={'scope': 'email'}
)

from app import views, models