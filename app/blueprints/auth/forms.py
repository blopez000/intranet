# app/blueprints/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=255)]
    )
    password = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=4, max=128)]
    )
    remember = BooleanField("Recordarme")
    next = HiddenField()  # opcional: para preservar ?next=...
    submit = SubmitField("Ingresar")
