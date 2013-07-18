from app import db
from hashlib import md5
from app import app
import flask.ext.whooshalchemy as whooshalchemy
from datetime import datetime
from flask import render_template, flash, redirect, session, url_for, request, g

ROLE_USER = 0
ROLE_ADMIN = 1
REQUEST_PENDING = 0
REQUEST_CONFIRM = 1

followers = db.Table('follwers', 
		db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
		db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
		)

#user class
class User(db.Model):

	#basic
	id = db.Column(db.Integer, primary_key = True)
	nickname = db.Column(db.String(64), index = True, unique = True)
	email = db.Column(db.String(120), index = True, unique = True)
	role = db.Column(db.SmallInteger, default = ROLE_USER)

	#third-party login
	weibo_id = db.Column(db.String(64), unique = True)
	weibo_img = db.Column(db.String(120), unique = True)
	facebook_id = db.Column(db.String(64), unique = True)
	renren_id = db.Column(db.String(64), unique = True)
	alipay_id = db.Column(db.String(64), unique = True)

	
	#back reference from current records
	borrow = db.relationship('Record', backref = 'borrows', lazy = 'dynamic', primaryjoin = ('Record.borrower_id == User.id'))
	lend = db.relationship('Record', backref = 'lends', lazy = 'dynamic', primaryjoin = ('Record.lender_id == User.id'))
	
	#back reference from history records
	his_borrow = db.relationship('History', backref = 'borrows', lazy = 'dynamic', primaryjoin = ('History.borrower_id == User.id'))
	his_lend = db.relationship('History', backref = 'lends', lazy = 'dynamic', primaryjoin = ('History.lender_id == User.id'))
	
	#back reference from friends request

	request_from = db.relationship('FriendRequest', backref = 'sends', lazy = 'dynamic', primaryjoin = ('FriendRequest.sender_id == User.id'))
	request_to = db.relationship('FriendRequest', backref = 'receives', lazy = 'dynamic', primaryjoin = ('FriendRequest.receiver_id == User.id'))

	about_me = db.Column(db.String(140))
	last_seen = db.Column(db.DateTime)

	#user-user relationship
	followed = db.relationship('User',
		secondary = followers,
		primaryjoin = (followers.c.follower_id == id),
		secondaryjoin = (followers.c.followed_id ==id),
		backref = db.backref('followers', lazy = 'dynamic'),
		lazy = 'dynamic')

	#login methods
	def is_authenticated(self):
		return True

	def is_active(self):
		return True

	def is_anonymous(self):
		return False

	# get id of an user
	def get_id(self):
		return unicode(self.id)

	# method that returns user from its id
	@staticmethod
	def from_id(id):
		u = User.query.filter_by(id = id).first()
		if u == None:
			return False
		else:
			return u 

	#get user's avatar
	def avatar(self, size):
		if self.weibo_img and self.weibo_img is not None:
			return self.weibo_img
		elif self.facebook_id and self.facebook_id is not None:
			return 'https://graph.facebook.com/' + str(self.facebook_id) + '/picture?width=' + str(size) + '&height=' + str(size)
		elif self.renren_id and self.renren_id is not None:
			pass
		elif self.alipay_id and self.alipay_id is not None:
			pass
		else:
			return 'http://www.gravatar.com/avatar/' + md5(self.email).hexdigest() + '?d=mm&s=' + str(size)

	#follow an user
	def follow(self, user):

		if user.is_following(self):
			self.followed.append(user)
			req = FriendRequest.query.\
				filter(FriendRequest.sender_id == user.id, FriendRequest.receiver_id == self.id)
			for r in req:
				db.session.delete(r)
			return self

		elif not self.is_following(user):
			self.followed.append(user)
			if not self == user:
				fr = FriendRequest(sender_id = self.id, receiver_id = user.id, timestamp = datetime.utcnow(), status = REQUEST_PENDING)
				db.session.add(fr)
				db.session.commit()
			return self


	#unfollow an user
	def unfollow(self, user):
		if self.is_following(user):
			self.followed.remove(user)
			return self

	#check if is following an user
	def is_following(self, user):
		return self.followed.filter(followers.c.followed_id == user.id).count() > 0

	#get posts that followed by user
	def followed_posts(self):
		return Post.query.join(followers, (followers.c.followed_id == Post.user_id)).filter(followers.c.follower_id == self.id).order_by(Post.timestamp.desc())

	#get borrowed records
	def borrow_records(self):
		return Record.query.filter_by(borrower_id = self.id).order_by(Record.timestamp.desc())

	#get user's lend records
	def lend_records(self):
		return Record.query.filter_by(lender_id = self.id).order_by(Record.timestamp.desc())

	#get user's borrow history
	def borrow_history(self):
		return History.query.filter_by(borrower_id = self.id).order_by(History.timestamp.desc())

	#get user's lend history
	def lend_history(self):
		return History.query.filter_by(lender_id = self.id).order_by(History.timestamp.desc())

	#get user's incoming request
	def incoming_requests(self):
		return FriendRequest.query.\
			filter(FriendRequest.receiver_id == self.id, FriendRequest.status == REQUEST_PENDING).order_by(FriendRequest.timestamp.desc())

	#return list of valid friends
	def valid_friends(self):
		valid = []
		friends = self.followed
		for f in friends:
			if f.is_following(self):
				valid.append(f)
		return valid
	
	def is_valid_friend(self, user):
		if user.is_following(self) and self.is_following(user):
			return True
		else:
			return False

	#return number of valid friends
	def valid_friends_number(self):
		valid = []
		friends = self.followed
		for f in friends:
			if f.is_following(self):
				valid.append(f)
		return len(valid)
	
	#return mutual friends between two users
	def mutual_friends(self, user):
		my_friends = self.valid_friends()
		user_friends = user.valid_friends()
		mutual_friends = []

		for f in my_friends:
			if user_friends.count(f) > 0:
				mutual_friends.append(f)
		return mutual_friends

	#generate a unique nickname for user
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

#record class(id, amount, timestamp, borrower_id, lender_id)
class Record(db.Model):
	__tablename__ = 'record_table'
	id = db.Column(db.Integer, primary_key = True)
	amount = db.Column(db.Integer)
	timestamp = db.Column(db.DateTime)
	borrower_id= db.Column(db.Integer, db.ForeignKey('user.id'))
	lender_id= db.Column(db.Integer, db.ForeignKey('user.id'))

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

#history class(same to record class)
class History(db.Model):
	__tablename__ = 'history_table'
	id = db.Column(db.Integer, primary_key = True)
	amount = db.Column(db.Integer)
	timestamp = db.Column(db.DateTime)
	borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	lender_id = db.Column(db.Integer, db.ForeignKey('user.id'))

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

class FriendRequest(db.Model):
	id = db.Column(db.Integer, primary_key = True)
	timestamp = db.Column(db.DateTime)
	sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
	status = db.Column(db.SmallInteger, default = REQUEST_PENDING)

	def __repr__(self):
		return '<FriendRequest %r>' % (self.id)
