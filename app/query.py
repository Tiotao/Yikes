from models import User, ROLE_USER, ROLE_ADMIN, REQUEST_PENDING, REQUEST_CONFIRM, FriendRequest, Record, History
from app import db
from flask import g, session
from datetime import datetime

class DataQuery(object):

	#user

	def init_user(self, nickname, email, role, weibo_id, weibo_img, facebook_id, renren_id, alipay_id):
		if nickname is None or nickname == "":
			nickname = email.split('@')[0]
		nickname = User.make_unique_nickname(nickname)
		user = User(nickname = nickname, email = email, role = role, weibo_id = weibo_id, weibo_img = weibo_img, facebook_id = facebook_id, renren_id = renren_id, alipay_id = alipay_id)
		db.session.add(user)
		db.session.add(user.follow(user))
		db.session.commit()
		return user

	def send_request(self, sender, receiver):
		if receiver.is_following(sender):
			req = self.find(FriendRequest, ['sender_id', 'receiver_id'], [receiver.id, sender.id]) 
			for r in req:
				db.session.delete(r)
				db.session.commit()
		elif not sender.is_following(receiver):
			if not receiver == sender:
				fr = FriendRequest(sender_id = sender.id, receiver_id = receiver.id, timestamp = datetime.utcnow(), status = REQUEST_PENDING)
				db.session.add(fr)
				db.session.commit()
		u = sender.follow(receiver)
		if u is None:
			return False
		else:
			db.session.add(u)
			db.session.commit()
			return True


	#update all data types
	def update(self, target, items, data):
		#update target.item => data
		#items and data must be two lists with same length.
		if len(items) != len(data):
			print "unacceptable data sand items input!"
			return False
		else:
			for i in range(0, len(items)):
				item = items[i]
				datam = data[i]
				setattr(target, item, datam)
			db.session.add(target)
			db.session.commit()
			return True

	#data filter
	def find(self, Type, items, data):
		#find entry with type Type and follows (item = datam)
		if len(items) != len(data):
			print "unacceptable data and items input!"
			return False
		else:
			criteria = {}
			for i in range(0, len(items)):
				criteria[str(items[i])] = data[i]
			return Type.query.\
				filter_by(**criteria)




