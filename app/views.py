from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from app import app, db, lm, oid
from forms import LoginForm, EditForm, PostForm, SearchForm, RecordForm
from models import User, ROLE_USER, ROLE_ADMIN, Post, Record
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
    form.lender.choices = friends
    flash(form.lender.data)

    if form.validate_on_submit():
        borrower = g.user
        lender = User().from_id(form.lender.data)
        temp_group = borrower.mutual_friends(lender)
        temp_group_id = []
        for u in temp_group:
            temp_group_id.append(str(u.id))

        nodes = temp_group_id
        records = Record.query.all()
        print "aaa", records
        
        edges_record = Record().get_records(temp_group_id)
        print "ddd" , edges_record
        edges = []
        weights = []
        
        for r in edges_record:
            print r
            edges.append((str(r.borrower_id), str(r.lender_id)))
            weights.append(r.amount)
            db.session.delete(r)

        req = UpdateRequest()
        req.form_graph(nodes, edges, weights)
        print "edge" , edges
        print req.group.nodes()

        req.add_record(str(borrower.id), str(lender.id), form.amount.data)
        
        new_records = req.all_edges()
        for rec in new_records:
            db.session.add(Record(amount = rec[2], timestamp = datetime.utcnow(), lender_id = int(rec[1]), borrower_id = int(rec[0])))

        db.session.commit()
        flash('Your record is now live!')
        return redirect(url_for('index'))
    borrow_records = g.user.borrow_records().paginate(page, RECORDS_PER_PAGE, False)
    lend_records = g.user.lend_records().paginate(page, RECORDS_PER_PAGE, False)
    return render_template("index.html",
        title = 'Home',
        form = form,
        borrow_records = borrow_records,
        lend_records = lend_records,)

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

@app.route('/user/<nickname>')
@app.route('/user/<nickname>/<int:page>')
@login_required
def user(nickname, page = 1):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname +' does not exist!' )
        return redirect(url_for('index'))
    borrow_records = g.user.borrow_records().paginate(page, RECORDS_PER_PAGE, False)
    lend_records = g.user.lend_records().paginate(page, RECORDS_PER_PAGE, False)
    return render_template('user.html', 
        user = user,
        borrow_records = borrow_records,
        lend_records = lend_records)

@app.route('/edit', methods = ['GET', 'POST'])
@login_required
def edit():
    form = EditForm(g.user.nickname)
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.about_me = form.about_me.data
        db.session.add(g.user)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    else:
        form.nickname.data = g.user.nickname
        form.about_me.data = g.user.about_me
        return render_template('edit.html', form = form)

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

@app.route('/search', methods = ['POST'])
@login_required
def search():
    if not g.search_form.validate_on_submit():
        return redirect(url_for('index'))
    return redirect(url_for('search_results', query = g.search_form.search.data))

@app.route('/search_results/<query>')
@login_required
def search_results(query):
    results = Post.query.whoosh_search(query, MAX_SEARCH_RESULTS).all()
    return render_template('search_results.html',
        query = query,
        results = results)

@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500
