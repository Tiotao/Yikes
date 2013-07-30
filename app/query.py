from models import User, ROLE_USER, ROLE_ADMIN, REQUEST_PENDING, REQUEST_CONFIRM, FriendRequest, Record, History
from app import db
from flask import g, session
from datetime import datetime
from main import UpdateRequest

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

	def be_friend(self, user1, user2):
		if user1 is None or user2 is None:
			print "none of the users shall be None"
			return False
		else:
			user1.follow(user2)
	        user2.follow(user1)
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

	#delete all data types
	def delete(self, target):
		if target is None:
			print "target does not exist"
			return False
		else:
			db.session.delete(target)
			db.session.commit()
			return True

	#data filter
	def find(self, Type, items, data):
		#find entry with type Type and follows (item = datam)
		if len(items) != len(data):
			print "unacceptable data and items input!"
			return False
		elif len(items) == 0:
			return Type.query.all()
		else:
			criteria = {}
			for i in range(0, len(items)):
				criteria[str(items[i])] = data[i]
			return Type.query.\
				filter_by(**criteria)


	#new record

	def new_record(self, borrower, lender, amount):

		if borrower is None or lender is None or amount is None:
			print "missing value"
			return False
		else:	
			time = datetime.utcnow()

			#add history record in database
			db.session.add(History(amount = amount, timestamp = time, lender_id = lender.id, borrower_id = borrower.id))

			#store mutual friends in temp_group => nodes
			temp_group = borrower.mutual_friends(lender)
			temp_group_id = []
			for u in temp_group:
			    temp_group_id.append(str(u.id))

			nodes = temp_group_id
			records = Record.query.all()

			#store related records in edges
			edges_record = Record().get_records(temp_group_id)
			edges = []
			weights = []

			for r in edges_record:
				edges.append((str(r.borrower_id), str(r.lender_id)))
				weights.append(r.amount)
				#delete existing records
				db.session.delete(r)
				db.session.commit()

			#create graph model from edges and nodes
			req = UpdateRequest()
			req.form_graph(nodes, edges, weights)

			#add new record into graph model
			req.add_record(str(borrower.id), str(lender.id), form.amount.data)

			#export edges from graph model
			new_records = req.all_edges()
			for rec in new_records:    
				#re-organize current record in database
				db.session.add(Record(amount = rec[2], timestamp = time, lender_id = int(rec[1]), borrower_id = int(rec[0])))
				db.session.commit()

			return True

