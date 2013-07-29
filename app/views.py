from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from app import app, db, lm, oid, oauth, facebook, client, url, dq
from forms import LoginForm, EditForm, SearchForm, RecordForm, QRForm
from models import User, ROLE_USER, ROLE_ADMIN, FriendRequest, Record, History
from datetime import datetime
from config import RECORDS_PER_PAGE
from main import UpdateRequest



@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()

#LOGIN
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
    user = dq.find(User, ['email'], [resp.email]).first()
    if user is None:
        user = dq.init_user(resp.nickname, resp.email, ROLE_USER, None, None, None, None, None)
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember = remember_me)
    return redirect(request.args.get('next') or url_for('index'))

#dev without internet
@app.route('/devlogin')
def devlogin():
    user = User.query.filter_by(nickname='tiotaocn').first()
    login_user(user, remember = True)
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

    next_url = request.args.get('next') or url_for('index')

    #for connecting user's acc with weibo acc
    if g.user is not None and g.user.is_authenticated():

        if r is None or r.access_token is None:
            flash('You denied the connection')
            return redirect(next_url)
        
        wb_id = client.account.get_uid.get()['uid']
        
        if User.query.filter_by(weibo_id=str(wb_id)).first() is None:
            dq.update(g.user, ['weibo_id'], [str(wb_id)])
            flash('You are now linked with %s' % client.users.show.get(uid=wb_id)['screen_name'])
        else:
            flash('Your weibo account has been linked previously')

        return redirect(url_for('settings'))

    #for login  
    else:

        if r is None or r.access_token is None:
            flash('You denied the login')
            return redirect(next_url)

        #user data from server
        wb_id = client.account.get_uid.get()['uid']
        wb_email = client.account.profile.email.get(access_token=access_token)['email']
        weibo_user = client.users.show.get(uid=uid)
        wb_nickname = weibo_user['screen_name']
        wb_img = weibo_user['avatar_large']

        user = User.query.filter_by(weibo_id=str(wb_id)).first()

        #cannot find a user with the current weibo id        
        if user is None:

            u = User.query.filter_by(email=wb_email).first()
            # email taken
            if u:
                login_user(u, remember = remember_me)
                return redirect(url)
            # email not taken
            else:
                dq.init_user(wb_nickname, wb_email, ROLE_USER, str(wb_id), wb_img, None, None, None)
                #client.statuses.update.post(status=u'test oauth2.0')

        remember_me = False
        
        if 'remember_me' in session:
            remember_me = session['remember_me']
            session.pop('remember_me', None)
        
        login_user(user, remember = remember_me)

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

    fb_user = facebook.get('/me')
    fb_id = me.data['id']
    fb_email = me.data['email']
    
    if fb_user.data['username']:
        fb_username = fb_user.data['username']
    else:
        fb_username = fb_user.data['name']

    #for connecting user's acc with facebook acc
    if g.user is not None and g.user.is_authenticated():
        if User.query.filter_by(facebook_id=str(fb_id)).first() is None:
            dq.update(g.user, ['facebook_id'], [str(fb_id)])
            flash('You are now linked with %s' % fb_username)
        else:
            flash('Your fb account has been linked previously')

        return redirect(url_for('settings'))

    #for new login
    user = User.query.filter_by(facebook_id=str(fb_id)).first()

    if user is None:
        u = User.query.filter_by(email=fb_email).first()        
        if u:
            login_user(u, remember = remember_me)
            return facebook.authorize(callback=url_for('facebook_callback',
                    next=request.args.get('next') or request.referrer or None,
                    _external=True))
        
        else:
            dq.init_user(fb_username, fb_email, ROLE_USER, None, None, str(fb_id), None, None)

    login_user(user, remember = remember_me)

    flash('You are now logged in as %s' % user.nickname)
    return redirect(url_for('index'))

@facebook.tokengetter
def get_facebook_oauth_token():
    return session.get('fb_access_token')   


@app.route('/deconnect/facebook')
def deconnect_facebook():
    dq.update(g.user, ['facebook_id'], [None])
    return redirect(url_for('settings'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

#PAGE SPECS

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

    #data
    borrow_records = g.user.borrow_history()
    lend_records = g.user.lend_history()
    friends = User.query.filter_by(nickname = nickname).first().valid_friends()


    form = EditForm(g.user.nickname)
    if form.validate_on_submit():
        dq.update(g.user, ['nickname', 'about_me'], [form.nickname.data, form.about_me.data])
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
        dq.update(g.user, ['nickname', 'about_me'], [form.nickname.data, form.about_me.data])
        flash('Your changes have been saved.')
        return redirect(url_for('user', nickname = g.user.nickname))
    else:
        edit_form.nickname.data = g.user.nickname
        edit_form.about_me.data = g.user.about_me

    return render_template('settings.html',
        edit_form = edit_form,
        sina_url = url)

#FRIENDING

@app.route('/follow/<nickname>')
def follow(nickname):
    user = dq.find(User, ['nickname'], [nickname]).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('index'))
    if user == g.user:
        flash('You can\'t follow yourself!')
        return redirect(url_for('user', nickname = nickname))

    request = dq.send_request(g.user, user)
    if request is False:
        flash('Cannot follow ' + nickname + '.')
        return redirect(url_for('user', nickname = nickname))
    else:
        if not user.is_valid_friend(g.user):
            flash('Your request has been sent to ' + nickname + '!')
        else:
            flash('You are now friend with ' + nickname + '!')
    return redirect(url_for('user', nickname = nickname))

@app.route('/unfollow/<nickname>')
def unfollow(nickname):
    user = dq.find(User, ['nickname'], [nickname]).first()
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

@app.route('/ignore_response/<id>')
@login_required
def ignore_response(id):
    req = FriendRequest.query.filter_by(id = id).first()
    sender = User().from_id(req.sender_id)
    nickname = g.user.nickname
    db.session.delete(req)
    db.session.commit()
    return redirect(url_for('user', nickname = nickname))


@app.route('/admin')
def admin():
    users = User.query.all()
    requests = FriendRequest.query.all()
    records = Record.query.all()
    histories = History.query.all()
    return render_template('admin.html', users=users, requests = requests, records = records, histories = histories)

#QR SERVICES

@app.route('/qrcode', methods= ['GET', 'POST'])
@login_required
def qrcode():
    form = QRForm(request.form)
    if form.validate_on_submit():
        amt = str(form.amt.data)
        bid = str(g.user.id)
        data = str('http://yikes.herokuapp.com/query/bid='+bid+',amt='+amt)
        imgurl = 'https://chart.googleapis.com/chart?chs=150x150&cht=qr&chl='+data+'&choe=UTF-8'
        return render_template('qrcode.html', imgurl = imgurl, form=form)
    return render_template('qrcode.html', imgurl = None, form=form)

@app.route('/query/bid=<bid>,amt=<amt>')
@login_required
def query(bid, amt):
    if bid and amt:
        borrower_id = int(bid)
        amount = int(amt)
        borrower = User().from_id(borrower_id)
        lender = g.user
        time = datetime.utcnow()

        if not g.user.is_valid_friend(borrower):
            g.user.follow(borrower)
            borrower.follow(g.user)
            db.session.commit()

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
        req.add_record(str(borrower.id), str(lender.id), amount)
        
        #export edges from graph model
        new_records = req.all_edges()
        for rec in new_records:    
            #re-organize current record in database
            db.session.add(Record(amount = rec[2], timestamp = time, lender_id = int(rec[1]), borrower_id = int(rec[0])))
            db.session.commit()

        return redirect(url_for('index'))

#ERROR HANDLERS

@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
