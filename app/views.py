from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from app import app, db, lm, oid, oauth, facebook, client, url
from forms import LoginForm, EditForm, PostForm, SearchForm, RecordForm, QRForm
from models import User, ROLE_USER, ROLE_ADMIN, FriendRequest, Record, History
from datetime import datetime
from config import RECORDS_PER_PAGE, MAX_SEARCH_RESULTS
from main import UpdateRequest


@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.route('/', methods = ['GET', 'POST'])
@app.route('/index', methods= ['GET', 'POST'])
@app.route('/index/<int:page>', methods = ['GET', 'POST'])
@login_required
def index(page = 1):
    form = RecordForm(request.form)
    friends = sorted([(c.id, c.nickname) for c in g.user.valid_friends()], key=lambda friend: friend[0])
    valid =[]

    for f in friends:
        if not int(f[0]) == int(g.user.id):
            valid.append(f)

    form.lender.choices = valid
    time = datetime.utcnow()
    if form.validate_on_submit():
        borrower = g.user
        lender = User().from_id(form.lender.data)

        #add history record in database
        db.session.add(History(amount = form.amount.data, timestamp = time, lender_id = form.lender.data, borrower_id = borrower.id))

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
            print "del: ", r
            db.session.delete(r)
            db.session.commit()

        #create graph model from edges and nodes
        req = UpdateRequest()
        for w in weights:
            print w
        req.form_graph(nodes, edges, weights)
        
        #add new record into graph model
        req.add_record(str(borrower.id), str(lender.id), form.amount.data)
        
        #export edges from graph model
        new_records = req.all_edges()
        for rec in new_records:    
            #re-organize current record in database
            print req.group.edge_weight(rec)
            db.session.add(Record(amount = rec[2], timestamp = time, lender_id = int(rec[1]), borrower_id = int(rec[0])))
            db.session.commit()
            print "add: ", rec

        
        flash('Your record is now live!')
        return redirect(url_for('index'))
    #borrow records and lend records
    borrow_records = g.user.borrow_records()#.paginate(page, RECORDS_PER_PAGE, False)
    lend_records = g.user.lend_records()#.paginate(page, RECORDS_PER_PAGE, False)
    return render_template("index.html",
        title = 'Home',
        form = form,
        borrow_records = borrow_records,
        lend_records = lend_records,)


#oid
@app.route('/login', methods = ['GET', 'POST'])
@oid.loginhandler
def login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('index'))
    form = LoginForm()

    if form.validate_on_submit():
        session['remember_me'] = form.remember_me.data
        return oid.try_login(form.openid.data, ask_for = ['nickname', 'email'])
    return render_template('login.html', 
        title = 'Sign In',
        form = form,
        providers = app.config['OPENID_PROVIDERS'])

@oid.after_login
def after_login(resp):
    if resp.email is None or resp.email == "":
        flash('Invalid Login. Please try again.')
        redirect(url_for('login'))
    user = User.query.filter_by(email = resp.email).first()
    if user is None:
        nickname = resp.nickname
        if nickname is None or nickname == "":
            nickname = resp.email.split('@')[0]
        nickname = User.make_unique_nickname(nickname)
        user = User(nickname = nickname, email = resp.email, role = ROLE_USER)
        db.session.add(user)
        db.session.commit()
        db.session.add(user.follow(user))
        db.session.commit()
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember = remember_me)
    return redirect(request.args.get('next') or url_for('index'))

#oauth for WEIBO
@app.route('/login/weibo')
def login_weibo():
    return redirect(url)


@app.route('/weibo_callback', methods = ['GET', 'POST'])
def weibo_callback():
    code = request.args.get('code')
    r = client.request_access_token(code)
    access_token = r.access_token
    expires_in = r.expires_in 
    session['wb_access_token'] = access_token
    session['wb_expires_in'] = expires_in
    client.set_access_token(access_token, expires_in)
    print client.account.profile.email.get(access_token)['email']

    next_url = request.args.get('next') or url_for('index')

    if g.user is not None and g.user.is_authenticated():
        print g.user
        if r is None or r.access_token is None:
            flash('You denied the connection')
            return redirect(next_url)
        
        uid = client.account.get_uid.get()['uid']
        
        if User.query.filter_by(weibo_id=str(uid)).first() is None:
            g.user.weibo_id = str(uid)
            db.session.add(g.user)
            db.session.commit()
            flash('You are now linked with %s' % client.users.show.get(uid=uid)['screen_name'])
        else:
            flash('Your weibo account has been linked previously')

        return redirect(url_for('settings'))
        
    else:

        if r is None or r.access_token is None:
            flash('You denied the login')
            return redirect(next_url)

        uid = client.account.get_uid.get()['uid']

        email = client.account.profile.email.get(access_token)['email']
        print uid
        print email

        user = User.query.filter_by(weibo_id=str(uid)).first()
        print user

        #cannot find a user with the current weibo id        
        if user is None:

            u = User.query.filter_by(email=email).first()
            # email taken
            if u:
                login_user(u, remember = remember_me)
                return redirect(url)
            # email not taken
            else:
                weibo_user = client.users.show.get(uid=uid)
                img = weibo_user['avatar_large']
                user = User(nickname = weibo_user['screen_name'], email = email, role = ROLE_USER, weibo_id = str(uid), weibo_img = img)
                db.session.add(user)
                db.session.commit()
                db.session.add(user.follow(user))
                db.session.commit()
                #client.statuses.update.post(status=u'test oauth2.0')

        remember_me = False
        
        if 'remember_me' in session:
            remember_me = session['remember_me']
            session.pop('remember_me', None)
        
        login_user(user, remember = remember_me)
        
        print user.email

        flash('You are now logged in as %s' % user.nickname)
        return redirect(url_for('index'))

@app.route('/deconnect/weibo')
def deconnect_weibo():
    g.user.weibo_id = None
    g.user.weibo_img = None
    db.session.add(g.user)
    db.session.commit()
    return redirect(url_for('settings'))


#oauth for FACEBOOK
@app.route('/login/facebook')
def login_facebook():
    return facebook.authorize(callback=url_for('facebook_callback',
        next=request.args.get('next') or request.referrer or None,
        _external=True))

@app.route('/facebook_callback')
@facebook.authorized_handler
def facebook_callback(resp):

    next_url = request.args.get('next') or url_for('index')

    if resp is None or 'access_token' not in resp:
        flash('You denied the login')
        return redirect(next_url)

    session['fb_access_token'] = (resp['access_token'], '')
    
    remember_me = False
    
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)

    me = facebook.get('/me')
    fb_id = me.data['id']
    fb_email = me.data['email']
    
    if me.data['username']:
        fb_username = me.data['username']
    else:
        fb_username = me.data['name']

    if g.user is not None and g.user.is_authenticated():
        if User.query.filter_by(facebook_id=str(fb_id)).first() is None:
            g.user.facebook_id = str(fb_id)
            db.session.add(g.user)
            db.session.commit()
            flash('You are now linked with %s' % fb_username)
        else:
            flash('Your fb account has been linked previously')

        return redirect(url_for('settings'))


    user = User.query.filter_by(facebook_id=str(fb_id)).first()
    print user
    
    if user is None:
        u = User.query.filter_by(email=fb_email).first()        
        if u:
            login_user(u, remember = remember_me)
            return facebook.authorize(callback=url_for('facebook_callback',
                    next=request.args.get('next') or request.referrer or None,
                    _external=True))
        
        else:
            user = User(nickname = fb_username, email = fb_email, role = ROLE_USER, facebook_id = str(fb_id))
            db.session.add(user)
            db.session.commit()
            db.session.add(user.follow(user))
            db.session.commit()

    login_user(user, remember = remember_me)
    
    print user.email

    flash('You are now logged in as %s' % user.nickname)
    return redirect(url_for('index'))

@facebook.tokengetter
def get_facebook_oauth_token():
    return session.get('fb_access_token')   


@app.route('/deconnect/facebook')
def deconnect_facebook():
    g.user.facebook_id = None
    db.session.add(g.user)
    db.session.commit()
    return redirect(url_for('settings'))



@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/social', methods= ['GET', 'POST'])
@login_required
def social():
    friends = User.query.filter_by(nickname = g.user.nickname).first().valid_friends()
    form = SearchForm(request.form)
    if form.validate_on_submit():
        nickname = form.search.data
        results = User.query.filter_by(nickname=nickname)
        count=results.count()
        return render_template('social.html', friends=friends, form=form, results=results, results_count=count)
    return render_template('social.html', friends=friends, form=form, results=None, results_count=-1)


@app.route('/notice', methods= ['GET', 'POST'])
@login_required
def notice():
    incoming_requests = g.user.incoming_requests()#.paginate(page, RECORDS_PER_PAGE, False)
    number_req = g.user.incoming_requests().count()
    return render_template('notice.html', incoming_requests = incoming_requests,
        number_req = number_req)

@app.route('/user/<nickname>', methods = ['GET', 'POST'])
@app.route('/user/<nickname>/<int:page>', methods = ['GET', 'POST'])
@login_required
def user(nickname, page = 1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname +' does not exist!' )
        return redirect(url_for('index'))
    borrow_records = g.user.borrow_history()#.paginate(page, RECORDS_PER_PAGE, False)
    lend_records = g.user.lend_history()#.paginate(page, RECORDS_PER_PAGE, False)
    friends = User.query.filter_by(nickname = nickname).first().valid_friends()

    form = EditForm(g.user.nickname)
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.about_me = form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('user', nickname = nickname))
    else:
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me

    return render_template('user.html',
        form = form,
        user = user,
        borrow_records = borrow_records,
        lend_records = lend_records,
        friends = friends)


@app.route('/settings', methods = ['GET', 'POST'])
@login_required

def settings():
    edit_form = EditForm(g.user.nickname)
    if edit_form.validate_on_submit():
        g.user.nickname = edit_form.nickname.data
        g.user.about_me = edit_form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('user', nickname = g.user.nickname))
    else:
        edit_form.nickname.data = g.user.nickname
        edit_form.about_me.data = g.user.about_me

    return render_template('settings.html',
        edit_form = edit_form,
        sina_url = url)



@app.route('/ignore_response/<id>')
@login_required
def ignore_response(id):
    req = FriendRequest.query.filter_by(id = id).first()
    sender = User().from_id(req.sender_id)
    nickname = g.user.nickname
    db.session.delete(req)
    db.session.commit()
    return redirect(url_for('user', nickname = nickname))


@app.route('/follow/<nickname>')
def follow(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t follow yourself!')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.follow(user)
    if u is None:
        flash('Cannot follow ' + nickname + '.')
        return redirect(url_for('user', nickname = nickname))
    db.session.add(u)
    db.session.commit()
    flash('You are now following ' + nickname + '!')
    return redirect(url_for('user', nickname = nickname))

@app.route('/unfollow/<nickname>')
def unfollow(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t unfollow yourself!')
        return redirect(url_for('user', nickname = nickname))
    u = g.user.unfollow(user)
    if u is None:
        flash('Cannot unfollow ' + nickname + '.')
        return redirect(url_for('user', nickname = nickname))
    db.session.add(u)
    db.session.commit()
    flash('You have stopped following ' + nickname + '.')
    return redirect(url_for('user', nickname = nickname))

@app.route('/admin')
def admin():
    users = User.query.all()
    requests = FriendRequest.query.all()
    records = Record.query.all()
    histories = History.query.all()
    return render_template('admin.html', users=users, requests = requests, records = records, histories = histories)

@app.route('/qrcode', methods= ['GET', 'POST'])
def qrcode():
    import qrcode
    from PIL import Image
    form = QRForm(request.form)
    if form.validate_on_submit():
        amt = str(form.amt.data)
        bid = str(g.user.id)
        data = str('http://yikes.herokuapp.com/query/bid='+bid+',amt='+amt)
        qr = qrcode.QRCode()
        qr.add_data(data)
        qr.make()
        img = qr.make_image()
        img.save('1.png', kind="PNG")
        return render_template('qrcode.html', img = '1.png', form=form)
    return render_template('qrcode.html', img = None, form=form)

@app.route('/query/bid=<bid>,amt=<amt>')
def query(bid, amt):
    if bid and amt:
        borrower_id = int(bid)
        amount = int(amt)
        borrower = User().from_id(borrower_id)
        lender = g.user
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
            print "del: ", r
            db.session.delete(r)
            db.session.commit()

        #create graph model from edges and nodes
        req = UpdateRequest()
        for w in weights:
            print w
        req.form_graph(nodes, edges, weights)
        
        #add new record into graph model
        req.add_record(str(borrower.id), str(lender.id), amount)
        
        #export edges from graph model
        new_records = req.all_edges()
        for rec in new_records:    
            #re-organize current record in database
            print req.group.edge_weight(rec)
            db.session.add(Record(amount = rec[2], timestamp = time, lender_id = int(rec[1]), borrower_id = int(rec[0])))
            db.session.commit()
            print "add: ", rec

        return redirect(url_for('index'))

@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
