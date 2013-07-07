from app import db
from hashlib import md5
from app import app
import flask.ext.whooshalchemy as whooshalchemy

ROLE_USER = 0
ROLE_ADMIN = 1

followers = db.Table('follwers', 
		db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
		db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
		)

class User(db.Model):

	id = db.Column(db.Integer, primary_key = True)
	nickname = db.Column(db.String(64), index = True, unique = True)
	email = db.Column(db.String(120), index = True, unique = True)
	role = db.Column(db.SmallInteger, default = ROLE_USER)
	borrow = db.relationship('Record', backref = 'borrows', lazy = 'dynamic', primaryjoin = ('Record.borrower_id == User.id'))
	lend = db.relationship('Record', backref = 'lends', lazy = 'dynamic', primaryjoin = ('Record.lender_id == User.id'))
	his_borrow = db.relationship('History', backref = 'borrows', lazy = 'dynamic', primaryjoin = ('History.borrower_id == User.id'))
	his_lend = db.relationship('History', backref = 'lends', lazy = 'dynamic', primaryjoin = ('History.lender_id == User.id'))
	about_me = db.Column(db.String(140))
	last_seen = db.Column(db.DateTime)
	#borrow_records = db.relationship('Record', backref = "borrows")
	#lend_records = db.relationship("Record", backref = db.backref("lends", lazy = 'dynamic'), primaryjoin = ('Record.lender_id == id'), lazy = 'dynamic')
	followed = db.relationship('User',
		secondary = followers,
		primaryjoin = (followers.c.follower_id == id),
		secondaryjoin = (followers.c.followed_id ==id),
		backref = db.backref('followers', lazy = 'dynamic'),
		lazy = 'dynamic')

	def is_authenticated(self):
		return True

	def is_active(self):
		return True

	def is_anonymous(self):
		return False

	def get_id(self):
		return unicode(self.id)

	@staticmethod
	def from_id(id):
		u = User.query.filter_by(id = id).first()
		if u == None:
			return False
		else:
			return u 

	def avatar(self, size):
		return 'http://www.gravatar.com/avatar/' + md5(self.email).hexdigest() + '?d=mm&s=' + str(size)

	def follow(self, user):
		if not self.is_following(user):
			self.followed.append(user)
			return self

	def unfollow(self, user):
		if self.is_following(user):
			self.followed.remove(user)
			return self

	def is_following(self, user):
		return self.followed.filter(followers.c.followed_id == user.id).count() > 0

	def followed_posts(self):
		return Post.query.join(followers, (followers.c.followed_id == Post.user_id)).filter(followers.c.follower_id == self.id).order_by(Post.timestamp.desc())

	def borrow_records(self):
		return Record.query.filter_by(borrower_id = self.id).order_by(Record.timestamp.desc())

	def lend_records(self):
		return Record.query.filter_by(lender_id = self.id).order_by(Record.timestamp.desc())

	def borrow_history(self):
		return History.query.filter_by(borrower_id = self.id).order_by(History.timestamp.desc())

	def lend_history(self):
		return History.query.filter_by(lender_id = self.id).order_by(History.timestamp.desc())

	def valid_friends(self):
		valid = []
		friends = self.followed
		for f in friends:
			if f.is_following(self):
				valid.append(f)
		return valid
	
	def mutual_friends(self, user):
		my_friends = self.valid_friends()
		user_friends = user.valid_friends()
		mutual_friends = []

		for f in my_friends:
			if user_friends.count(f) > 0:
				mutual_friends.append(f)
		return mutual_friends

	@staticmethod
	def make_unique_nickname(nickname):
		if User.query.filter_by(nickname = nickname).first() == None:
			return nickname
		version = 2
		while True:
			new_nickname = nickname + str(version)
			if User.query.filter_by(nickname = new_nickname).first() == None:
				break
			version += 1
		return new_nickname

	def __repr__(self):
		return '<User %r>' % (self.nickname)

class Post(db.Model):

	id = db.Column(db.Integer, primary_key = True)
	body = db.Column(db.String(140))
	timestamp = db.Column(db.DateTime)
	user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

	def __repr__(self):
		return '<Post %r>' % (self.body)

class Record(db.Model):
	__tablename__ = 'record_table'
	id = db.Column(db.Integer, primary_key = True)
	amount = db.Column(db.Integer)
	timestamp = db.Column(db.DateTime)
	borrower_id= db.Column(db.Integer, db.ForeignKey('user.id'))
	lender_id= db.Column(db.Integer, db.ForeignKey('user.id'))
	#db.Column(db.Integer, db.ForeignKey(User.id))

	@staticmethod
	def get_records(users):
		all_records = Record.query.all()
		print "all: " , all_records
		records = []
		for x in all_records:
			print "borrower_id: ", x.borrower_id
			print "lender_id: ", x.lender_id
			print "users: ", users.count(x.borrower_id)
			if users.count(str(x.borrower_id)) > 0 and users.count(str(x.lender_id)) > 0:
				records.append(x)

		return records 

	def __repr__(self):
		return '<Record %r>' % (self.amount)


class History(db.Model):
	__tablename__ = 'history_table'
	id = db.Column(db.Integer, primary_key = True)
	amount = db.Column(db.Integer)
	timestamp = db.Column(db.DateTime)
	borrower_id= db.Column(db.Integer, db.ForeignKey('user.id'))
	lender_id= db.Column(db.Integer, db.ForeignKey('user.id'))
	#db.Column(db.Integer, db.ForeignKey(User.id))

	@staticmethod
	def get_records(users):
		all_records = History.query.all()
		print "all: " , all_records
		records = []
		for x in all_records:
			print "borrower_id: ", x.borrower_id
			print "lender_id: ", x.lender_id
			print "users: ", users.count(x.borrower_id)
			if users.count(str(x.borrower_id)) > 0 and users.count(str(x.lender_id)) > 0:
				records.append(x)

		return records 

	def __repr__(self):
		return '<History %r>' % (self.amount)
