from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL, Length, ValidationError, Email, Regexp
from flask_ckeditor import CKEditorField


# TODO: Create a RegisterForm to register new users
def starts_with_capital_for_author(form, field):
    words = field.data.split()
    for word in words:
        first_char = word[0]
        if not (first_char.isupper() and not any(char.isdigit() for char in word)):
            raise ValidationError("Each word should start with a capital letter, can't contain numbers!")


class RegisterForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=6), starts_with_capital_for_author])
    email = StringField("Email", validators=[Email(), DataRequired()])
    password = StringField('Password', [DataRequired(), Length(min=10), Regexp(
        regex='^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]+$',
        message='Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character.'
    )])  # TODO: Create a LoginForm to login existing users
    submit = SubmitField("Sign Up")


class LogInForm(FlaskForm):
    email = StringField("Email", validators=[Email(), DataRequired()])
    password = PasswordField('Password', [DataRequired()])  # TODO: Create a LoginForm to login existing users
    submit = SubmitField("Log In")


class Delete(FlaskForm):
    delete = SubmitField("Delete My Account")


class DeletePost(FlaskForm):
    delete = SubmitField("Delete This Post")


class Reset(FlaskForm):
    password = StringField('New_password', [DataRequired(), Regexp(
        regex='^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]+$',
        message='Password must contain at least one uppercase letter, one lowercase letter, one number, and one special character')])
    password_confirm = StringField('Confirm Password', [DataRequired()])
    submit = SubmitField("Reset")


class Send(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField("Send Code")


class Code(FlaskForm):
    code = StringField("Enter code that we've sent")
    confirm = SubmitField("Confirm")


class CommentForm(FlaskForm):
    body = CKEditorField('Comment', validators=[DataRequired(), Length(min=30, max=100)])
    submit = SubmitField("Submit Comment")
