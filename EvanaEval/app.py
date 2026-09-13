# EvanaEval/app.py
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    def __repr__(self):
        return f'<Category {self.name}>'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(10,2), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    description = db.Column(db.String(200))
    category = db.relationship('Category', backref=db.backref('transactions', lazy=True))
    def __repr__(self):
        return f'<Transaction {self.amount} {self.date}>'

# Forms
class TransactionForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=-1000000, max=1000000)])
    date = DateField('Date', validators=[DataRequired()], default=datetime.today)
    category = SelectField('Category', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save')

# Routes
@app.route('/')
def index():
    # Dashboard
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expense = sum(-t.amount for t in transactions if t.amount < 0)
    balance = total_income - total_expense
    return render_template('index.html', transactions=transactions, total_income=total_income, total_expense=total_expense, balance=balance)

@app.route('/add', methods=['GET', 'POST'])
def add_transaction():
    form = TransactionForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        t = Transaction(amount=form.amount.data, date=form.date.data, category_id=form.category.data, description=form.description.data)
        db.session.add(t)
        db.session.commit()
        flash('Transaction added')
        return redirect(url_for('index'))
    return render_template('transaction_form.html', form=form, title='Add Transaction')

@app.route('/edit/<int:tid>', methods=['GET', 'POST'])
def edit_transaction(tid):
    t = Transaction.query.get_or_404(tid)
    form = TransactionForm(obj=t)
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        t.amount = form.amount.data
        t.date = form.date.data
        t.category_id = form.category.data
        t.description = form.description.data
        db.session.commit()
        flash('Transaction updated')
        return redirect(url_for('index'))
    return render_template('transaction_form.html', form=form, title='Edit Transaction')

@app.route('/delete/<int:tid>', methods=['POST'])
def delete_transaction(tid):
    t = Transaction.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    flash('Transaction deleted')
    return redirect(url_for('index'))

@app.route('/filter', methods=['GET', 'POST'])
def filter_transactions():
    categories = Category.query.all()
    selected_category = request.args.get('category', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    query = Transaction.query
    if selected_category:
        query = query.filter_by(category_id=selected_category)
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    transactions = query.order_by(Transaction.date.desc()).all()
    return render_template('filter.html', transactions=transactions, categories=categories, selected_category=selected_category, start_date=start_date, end_date=end_date)

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# CLI command to init db
@app.cli.command('init-db')
def init_db():
    db.create_all()
    # Add default categories
    for name in ['Income', 'Food', 'Rent', 'Utilities', 'Entertainment']:
        if not Category.query.filter_by(name=name).first():
            db.session.add(Category(name=name))
    db.session.commit()
    print('Database initialized')

if __name__ == '__main__':
    app.run(debug=True)
