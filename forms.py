from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, validators

class UserForm(FlaskForm):
    first_name = StringField('First Name', [validators.DataRequired(), validators.Length(max=64)])
    last_name = StringField('Last Name', [validators.DataRequired(), validators.Length(max=64)])
    email = StringField('Email', [validators.Optional(), validators.Email()])
    password = PasswordField('Password', [validators.DataRequired(), validators.Length(min=6)])
    submit = SubmitField('Create User')

class GroupForm(FlaskForm):
    group_name = StringField('Group Name', [validators.DataRequired(), validators.Length(max=64)])
    group_description = StringField('Description', [validators.Optional(), validators.Length(max=256)])
    submit = SubmitField('Create Group')
