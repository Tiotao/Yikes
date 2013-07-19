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
    consumer_key='180236948816069',
    consumer_secret='becbcdbb934c58dae6e4305798d89b00',
    request_token_params={'scope': 'email'}
)

from weibo import APIClient

APP_KEY = '3525956681'            # app key
APP_SECRET = 'a26ea31dc385ed540b8f141f91087734'      # app secret
CALLBACK_URL = 'http://yikes.herokuapp.com/weibo_callback'  # callback url

client = APIClient(app_key=APP_KEY, app_secret=APP_SECRET,
                   redirect_uri=CALLBACK_URL, scope='email')
url = client.get_authorize_url()    # redirect the user to `url'

from app import views, models