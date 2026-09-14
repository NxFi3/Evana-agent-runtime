# EvanaEval/app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange

class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=64)])
    submit = SubmitField('Save')

class TransactionForm(FlaskForm):
    description = StringField('Description', validators=[DataRequired(), Length(max=128)])
    amount = FloatField('Amount', validators=[DataRequired(), NumberRange()])
    date = DateField('Date', default=None, validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save')
