from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, SelectField, SubmitField
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
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    category = db.relationship('Category', backref=db.backref('transactions', lazy=True))
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    def __repr__(self):
        return f'<Transaction {self.id} {self.type} {self.amount}>'

# Forms
class TransactionForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    date = DateField('Date', validators=[DataRequired()], default=datetime.utcnow)
    description = StringField('Description', validators=[Optional()])
    category = SelectField('Category', coerce=int, validators=[Optional()])
    type = SelectField('Type', choices=[('income', 'Income'), ('expense', 'Expense')], validators=[DataRequired()])
    submit = SubmitField('Save')

class CategoryForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField('Save')

# Helper to populate category choices
def populate_category_choices(form):
    form.category.choices = [(0, 'None')] + [(c.id, c.name) for c in Category.query.order_by('name')]

# Routes
@app.route('/')
def dashboard():
    income_total = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.type=='income').scalar() or 0
    expense_total = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.type=='expense').scalar() or 0
    balance = income_total - expense_total
    recent = Transaction.query.order_by(Transaction.date.desc()).limit(10).all()
    return render_template('dashboard.html', income=income_total, expense=expense_total, balance=balance, recent=recent)

@app.route('/transactions')
def transactions():
    category_id = request.args.get('category', type=int)
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    query = Transaction.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date <= end)
        except ValueError:
            pass
    transactions = query.order_by(Transaction.date.desc()).all()
    categories = Category.query.order_by('name').all()
    return render_template('transactions.html', transactions=transactions, categories=categories, selected_category=category_id, start_date=start_date, end_date=end_date)

@app.route('/transactions/new', methods=['GET', 'POST'])
def new_transaction():
    form = TransactionForm()
    populate_category_choices(form)
    if form.validate_on_submit():
        cat_id = form.category.data if form.category.data != 0 else None
        t = Transaction(amount=form.amount.data, date=form.date.data, description=form.description.data, category_id=cat_id, type=form.type.data)
        db.session.add(t)
        db.session.commit()
        flash('Transaction added', 'success')
        return redirect(url_for('transactions'))
    return render_template('transaction_form.html', form=form, title='New Transaction')

@app.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
def edit_transaction(id):
    t = Transaction.query.get_or_404(id)
    form = TransactionForm(obj=t)
    populate_category_choices(form)
    if form.validate_on_submit():
        t.amount = form.amount.data
        t.date = form.date.data
        t.description = form.description.data
        t.category_id = form.category.data if form.category.data != 0 else None
        t.type = form.type.data
        db.session.commit()
        flash('Transaction updated', 'success')
        return redirect(url_for('transactions'))
    return render_template('transaction_form.html', form=form, title='Edit Transaction')

@app.route('/transactions/<int:id>/delete', methods=['POST'])
def delete_transaction(id):
    t = Transaction.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Transaction deleted', 'success')
    return redirect(url_for('transactions'))

# Category routes
@app.route('/categories')
def categories():
    cats = Category.query.order_by('name').all()
    return render_template('categories.html', categories=cats)

@app.route('/categories/new', methods=['GET', 'POST'])
def new_category():
    form = CategoryForm()
    if form.validate_on_submit():
        cat = Category(name=form.name.data)
        db.session.add(cat)
        try:
            db.session.commit()
            flash('Category added', 'success')
            return redirect(url_for('categories'))
        except Exception:
            db.session.rollback()
            flash('Category name must be unique', 'danger')
    return render_template('category_form.html', form=form, title='New Category')

@app.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
def edit_category(id):
    cat = Category.query.get_or_404(id)
    form = CategoryForm(obj=cat)
    if form.validate_on_submit():
        cat.name = form.name.data
        try:
            db.session.commit()
            flash('Category updated', 'success')
            return redirect(url_for('categories'))
        except Exception:
            db.session.rollback()
            flash('Category name must be unique', 'danger')
    return render_template('category_form.html', form=form, title='Edit Category')

@app.route('/categories/<int:id>/delete', methods=['POST'])
def delete_category(id):
    cat = Category.query.get_or_404(id)
    if cat.transactions:
        flash('Cannot delete category with transactions', 'danger')
        return redirect(url_for('categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted', 'success')
    return redirect(url_for('categories'))

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# CLI command to create db
@app.cli.command('initdb')
def initdb_command():
    db.create_all()
    print('Initialized the database.')

if __name__ == '__main__':
    app.run(debug=True)
