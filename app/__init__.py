import os
from flask.ext.login import LoginManager
from flask.ext.openid import OpenID
from flask.ext.heroku import Heroku
from config import basedir
from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
engine = create_engine('')

app = Flask(__name__)
heroku = Heroku(app)
app.config.from_object('config')
db = create_engine('postgresql://nqblmxqesvbcjb:Q12QFIfpSaNqOJtp0KShFwmFN5@ec2-107-20-201-165.compute-1.amazonaws.com:5432/d7vao9hm2qoc3a')
lm = LoginManager()
lm.setup_app(app)
lm.login_view = 'login'
oid = OpenID(app, os.path.join(basedir, 'tmp'))

from app import views, models

