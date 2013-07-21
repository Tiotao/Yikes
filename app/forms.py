from flask.ext.wtf import Form, TextField, BooleanField, TextAreaField, SelectField, DecimalField, IntegerField
from flask.ext.wtf import Required, Length
from app.models import User, Record

#for openid login
class LoginForm(Form):
	openid = TextField('openid', validators = [Required()])
	remember_me = BooleanField('remember_me', default = False)

#for edit profile
class EditForm(Form):
	nickname = TextField('nickname', validators = [Required()])
	about_me = TextAreaField('about_me', validators = [Length(min = 0, max = 140)])
	
	def __init__(self, original_nickname, *args, **kwargs):
		Form.__init__(self, *args, **kwargs)
		self.original_nickname = original_nickname

	def validate(self):
		if not Form.validate(self):
			return False
		if self.nickname.data == self.original_nickname:
			return True
		user = User.query.filter_by(nickname = self.nickname.data).first()
		if user != None:
			self.nickname.errors.append('This nickname is already in use. Please choose another one.')
			return False
		return True

#for generating QR Code
class QRForm(Form):
	amt = IntegerField('amt', validators = [Required()])

#for search username
class SearchForm(Form):
	search = TextField('search', validators = [Required()])

#for add borrow record
class RecordForm(Form):
	amount = IntegerField('amount', validators = [Required()])
	lender = SelectField('lender', choices=[], coerce=int)