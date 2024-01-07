import smtplib
from bs4 import BeautifulSoup
from functools import wraps
from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory, session, abort
from flask_sqlalchemy import SQLAlchemy
import requests
import random
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_ckeditor import CKEditor, CKEditorField
from flask_bootstrap import Bootstrap5
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from sqlalchemy.orm import relationship
from wtforms.validators import DataRequired, Length, ValidationError, URL
import re
import datetime
import time
from sqlalchemy.exc import IntegrityError
from forms import RegisterForm, LogInForm, Delete, Reset, DeletePost, Send, Code, CommentForm
import string
import hashlib
import os
from email.mime.text import MIMEText
from email.header import Header

app = Flask(__name__)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


urls = requests.get(
    url="https://api.npoint.io/f07a1225405aaeaa0037").json()
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("URL")  # Example URI for the default database

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
db = SQLAlchemy()
db.init_app(app)
ckeditor = CKEditor(app)
bootstrap = Bootstrap5(app)


def admin_only(f):
    email = os.environ.get("EMAIL")

    @wraps(f)
    def decorated_fun(*args, **kwargs):
        if current_user.is_authenticated:  # if a user is logged in
            if current_user.email != email:  # and is not the admin
                return abort(403)
        else:  # random stranger
            return abort(403)
        return f(*args, **kwargs)  # only option left is the admin

    return decorated_fun


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))
    avatar = db.Column(db.String(500))  # New field for avatar URL
    posts = relationship("BlogPost", back_populates='author')
    comments = relationship("Comment", back_populates='comment_author')


# CONFIGURE TABLE
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="posts", lazy="joined")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_author = relationship("User", back_populates="comments", lazy="joined")

    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)


with app.app_context():
    db.create_all()


class CreateBlogForm(FlaskForm):
    def starts_with_single_capital(form, field):
        words = field.data.split()
        first_word = words[0] if words else None

        if first_word and not (first_word[0].isupper() or first_word[0].isdigit()):
            raise ValidationError('The content should start with a capital letter or a number!')

    def starts_with_capital_for_title(form, field):
        words = field.data.split()
        for word in words:
            first_char = word[0]
            if not (first_char.isupper() or first_char.isdigit()):
                raise ValidationError('Each word should start with a capital letter or a number!')

    def starts_with_capital_for_author(form, field):
        words = field.data.split()
        for word in words:
            first_char = word[0]
            if not (first_char.isupper() and not any(char.isdigit() for char in word)):
                raise ValidationError("Each word should start with a capital letter, can't contain numbers!")

    def validate_url(form, field):
        url = field.data
        if not 'https://images.unsplash.com/photo-' in url:
            raise ValidationError('Please provide a URL from Unsplash.')

    def check_for_spam(form, field):
        data = field.data

        # Calculate word count and unique character ratio
        words = data.split()
        word_count = len(words)

        unique_chars = len(set(data.replace(" ", "")))
        total_chars = len(data.replace(" ", ""))
        unique_ratio = unique_chars / max(1, total_chars)

        # Adjust these ratios based on your spam detection needs
        max_word_count = 10
        min_unique_ratio = 0.3

        # Check for spam-like content
        if word_count > max_word_count or unique_ratio < min_unique_ratio:
            raise ValidationError('Please provide meaningful content')

    title = StringField('Blog Post Title', validators=[DataRequired(), Length(min=10, max=40), check_for_spam,
                                                       starts_with_capital_for_title])
    subtitle = StringField('Subtitle', validators=[DataRequired(), Length(min=10, max=50), check_for_spam,
                                                   starts_with_single_capital])
    img_url = StringField("Img's URL (From unsplash.com)", validators=[DataRequired(), validate_url])
    body = CKEditorField('Blog Content', validators=[DataRequired(), Length(min=100)])  # <--
    submit = SubmitField('Submit Post')


class DeleteForm(FlaskForm):
    delete = SubmitField("Delete")


@app.route('/')
def home():
    email = os.environ.get("EMAIL")

    with app.app_context():
        result = db.session.execute(db.select(BlogPost).order_by(BlogPost.title))
        posts = result.scalars().all()

    url = random.choice(urls)
    return render_template("index.html", all_posts=posts, url=url, email=email)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    try:
        if form.validate_on_submit():
            password = request.form['password']
            email = request.form['email']
            hashed_password = generate_password_hash(password=password, method="pbkdf2:sha256", salt_length=8)
            hashed_email = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
            gravatar_url = f"https://www.gravatar.com/avatar/{hashed_email}?d=identicon"
            with app.app_context():
                new_user = User(name=request.form['name'], email=request.form['email'], password=hashed_password,
                                avatar=gravatar_url)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('home'))
    except IntegrityError:
        form.email.data = ''  # Clear the 'title' field
        flash('The user with such email already exists.')
    return render_template("register.html", form=form)


@app.route('/forgot_password', methods=['POST', "GET"])
def forgot_password():
    form = Send()
    if form.validate_on_submit():
        with app.app_context():
            user = db.session.execute(db.select(User).where(User.email == request.form.get('email'))).scalar()
            print(user)
            if not user:
                flash("The email wasn't found in the database.")
            else:
                session['email'] = user.email
                print(session['email'])

                def generate_random_code():
                    characters = string.ascii_letters + string.digits  # combining letters and digits
                    code = ''.join(random.choices(characters, k=6))  # generating a 6-character code
                    return code

                code = generate_random_code()
                session['code'] = code

                with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
                    testing_email = "niktestpython@gmail.com"
                    password = os.environ.get("PASSWORD")
                    connection.starttls()
                    connection.login(user=testing_email, password=password)
                    connection.sendmail(
                        from_addr=testing_email,
                        to_addrs=request.form['email'],
                        msg=f"Subject:Confirmation code.\n\nConfirmation code: {code}")
                    return render_template("send.html", form=form, msg_sent=True)

    return render_template("send.html", form=form)

    # Check if the 'Send Code' button was pressed


@app.route('/forgot_password/verification', methods=['POST', "GET"])
def code():
    form = Code()
    entered_code = form.code.data
    if form.validate_on_submit():
        attempts = session.get('attempts', 0)
        if entered_code == session.get('code'):
            email = session.get('email')
            with app.app_context():
                user = db.session.execute(db.select(User).where(User.email == email)).scalar()
                print(user)
            login_user(user)
            time.sleep(1)
            return redirect(url_for('reset'))
        else:
            attempts += 1
            print(attempts)
            session['attempts'] = attempts
            if attempts >= 6:
                time.sleep(2)
                flash("Too many attempts. Try again now.")
                session['attempts'] = 0  # Reset attempts count in session to zero
                return redirect(url_for('forgot_password'))
            flash("Codes aren't matching, try again.")
    return render_template("codes.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LogInForm()
    if form.validate_on_submit():
        email = request.form['email']
        password = request.form['password']
        with app.app_context():
            user = db.session.execute(db.select(User).where(User.email == email)).scalar()
            if not user:
                flash("The email wasn't found in the database.")
            else:
                if check_password_hash(password=password, pwhash=user.password) == True:
                    login_user(user)
                    return redirect(url_for('home'))
                else:
                    flash('Wrong password, try again.')
    return render_template("login.html", form=form)


def only_commenter(function):
    @wraps(function)
    def check(*args, **kwargs):
        user = db.session.execute(db.select(Comment).where(Comment.author_id == current_user.id)).scalar()
        if not current_user.is_authenticated or current_user.id != user.author_id:
            return abort(403)
        return function(*args, **kwargs)

    return check


@app.route('/delete_comment/<id>/<post_id>')
@only_commenter
def delete_comment(id, post_id):
    with app.app_context():
        comment_to_delete = db.session.execute(db.select(Comment).where(Comment.id == id)).scalar()
        db.session.delete(comment_to_delete)
        db.session.commit()
    return redirect(url_for('read_post', index=post_id))


@app.route('/delete', methods=['POST', "GET"])
@login_required
def delete():
    delete_form = Delete()
    if request.method == "POST" and delete_form.validate_on_submit():
        with app.app_context():
            user = db.session.execute(db.select(User).where(User.id == current_user.id)).scalar()
            comments_to_delete = db.session.execute(
                db.select(Comment).where(Comment.author_id == current_user.id)).scalars().all()
            posts_to_delete = db.session.execute(
                db.select(BlogPost).where(BlogPost.author_id == current_user.id)).scalars().all()
            for i in posts_to_delete:
                db.session.delete(i)  # or book_to_delete = db.get_or_404(Book, book_id)

            for i in comments_to_delete:
                db.session.delete(i)  # or book_to_delete = db.get_or_404(Book, book_id)
            db.session.delete(user)
            db.session.commit()
        return render_template("delete.html", form=delete_form, delete=True)

    return render_template("delete.html", form=delete_form)


@app.route('/reset', methods=['POST', "GET"])
@login_required
def reset():
    form = Reset()
    if form.validate_on_submit() and request.method == "POST":
        email = current_user.email
        password = request.form['password']
        confirm_password = request.form['password_confirm']
        if password == confirm_password:
            with app.app_context():
                user_with_new_password = db.session.execute(db.select(User).where(User.email == email)).scalar()
                hashed_password = generate_password_hash(password=password, method="pbkdf2:sha256", salt_length=8)

                user_with_new_password.password = hashed_password
                db.session.commit()
                return render_template("reset.html", msg_sent=True, form=form)
        else:
            flash("Passwords aren't matches, try again.")

    return render_template("reset.html", form=form)


@app.route("/post/<int:index>", methods=["GET", "POST"])
def read_post(index):
    email = os.environ.get("EMAIL")
    form = CommentForm()
    with app.app_context():
        post = db.session.execute(db.select(BlogPost).where(BlogPost.id == index)).scalar()
    requested_post = db.get_or_404(BlogPost, index)
    blog_id = post.id
    blog_title = post.title
    blog_body = post.body
    blog_image = post.img_url
    blog_author = post.author.name
    blog_date = post.date
    blog_subtitle = post.subtitle
    soup = BeautifulSoup(blog_body, 'html.parser')
    for img_tag in soup.find_all('img'):
        try:
            del img_tag['style']  # Remove style attribute with height and width
        except Exception:
            pass
        img_tag['class'] = img_tag.get('class', []) + ['img-fluid']
    modified_blog_body = str(soup)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=request.form['body'],
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('read_post', index=index))

    return render_template("post.html", title=blog_title, body=modified_blog_body, subtitle=blog_subtitle,
                           url=blog_image,
                           author=blog_author, date=blog_date, id=blog_id, form=form, post=requested_post, email=email)


# @app.route("/post/<int:index>")
# def read_post(index):
#     blog_title = all_posts[index-1]['title']
#     blog_body = all_posts[index-1]['body']
#     return render_template("post.html", title=blog_title, body=blog_body)
@app.route("/about_us")
def about():
    return render_template("about.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/contact_with_us", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        message = request.form['message']
        subject = f"New message from {name}"
        email_content = f"Name: {name}\nEmail: {email}\nPhone Number: {phone}\nMessage: {message}"

        msg = MIMEText(email_content, 'plain', 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            testing_email = "niktestpython@gmail.com"
            password = os.environ.get("PASSWORD")
            connection.starttls()
            connection.login(user=testing_email, password=password)
            connection.sendmail(
                from_addr=testing_email,
                to_addrs="ppnikita52@gmail.com",
                msg=msg.as_string())
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)


@app.route("/new_post", methods=["GET", "POST"])
@admin_only
def new_post():
    form = CreateBlogForm()
    if form.validate_on_submit():
        try:
            title = request.form['title']
            subtitle = request.form['subtitle']
            img_url = request.form['img_url']
            body = request.form['body']
            date = datetime.datetime.now()
            formatted_date = date.strftime("%B %d, %Y")
            print(body)
            print(title)
            print(img_url)
            print(formatted_date)
            with app.app_context():
                new_post = BlogPost(
                    title=title,
                    subtitle=subtitle,
                    date=formatted_date,
                    author=current_user,
                    img_url=img_url,
                    body=body
                )
                db.session.add(new_post)
                db.session.commit()
                time.sleep(1)
            return redirect(url_for('home'))
        except IntegrityError:
            form.title.data = ''  # Clear the 'title' field
            return render_template("make-post.html", url=random.choice(urls), form=form, msg_sent=True)

    return render_template("make-post.html", url=random.choice(urls), form=form)


@app.route("/edit-post/<post_id>", methods=["POST", "GET"])
@admin_only
def edit(post_id):
    with app.app_context():
        post = db.session.execute(db.select(BlogPost).where(BlogPost.id == post_id)).scalar()
    title = post.title
    subtitle = post.subtitle
    body = post.body
    print(body)
    url = post.img_url
    date = post.date
    author = post.author
    form = CreateBlogForm(title=post.title, subtitle=post.subtitle, img_url=post.img_url, authors_name=post.author,
                          body=post.body)
    if form.validate_on_submit():
        with app.app_context():
            post_to_update = db.session.execute(db.select(BlogPost).where(BlogPost.id == post_id)).scalar()
            # or book_to_update = db.get_or_404(Book, book_id)  
            post_to_update.title = request.form['title']
            post_to_update.subtitle = request.form['subtitle']
            post_to_update.img_url = request.form['img_url']
            post_to_update.body = request.form['body']
            db.session.commit()
            time.sleep(1)
            new_post_id = int(post_id)
            return redirect(url_for("read_post", index=new_post_id))
    return render_template("make-post.html", edit_post=True, form=form, url=url)


@app.route("/are_you_sure/<int:id>/<name>", methods=["POST", "GET"])
@admin_only
def are_you_sure(id, name):
    form = DeletePost()
    if request.method == "POST":
        with app.app_context():
            post_to_delete = db.session.execute(db.select(BlogPost).where(BlogPost.id == id)).scalar()
            # or book_to_delete = db.get_or_404(Book, book_id)
            db.session.delete(post_to_delete)
            db.session.commit()
            time.sleep(1)
        return redirect(url_for("home"))
    return render_template("are_you_sure.html", form=form, id=id, name=name)


if __name__ == "__main__":
    app.run(debug=False)
