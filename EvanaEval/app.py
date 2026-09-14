from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, TextAreaField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<Category {self.name}>'

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref=db.backref('transactions', lazy=True))
    type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'

    def __repr__(self):
        return f'<Transaction {self.amount} {self.type}>'

class TransactionForm(FlaskForm):
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0.01)])
    description = TextAreaField('Description', validators=[Optional()])
    date = DateField('Date', validators=[DataRequired()], default=datetime.utcnow)
    category = SelectField('Category', coerce=int, validators=[Optional()])
    type = SelectField('Type', choices=[('income', 'Income'), ('expense', 'Expense')], validators=[DataRequired()])
    submit = SubmitField('Save')

@app.before_first_request
def create_tables():
    db.create_all()
    # Ensure at least one category exists
    if not Category.query.first():
        db.session.add(Category(name='Uncategorized'))
        db.session.commit()

@app.route('/')
def dashboard():
    income_total = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.type=='income').scalar() or 0
    expense_total = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.type=='expense').scalar() or 0
    balance = income_total - expense_total
    return render_template('dashboard.html', income=income_total, expense=expense_total, balance=balance)

@app.route('/transactions')
def transaction_list():
    category_id = request.args.get('category', type=int)
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    query = Transaction.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    transactions = query.order_by(Transaction.date.desc()).all()
    categories = Category.query.all()
    return render_template('transaction_list.html', transactions=transactions, categories=categories, selected_category=category_id, start_date=start_date, end_date=end_date)

@app.route('/transactions/new', methods=['GET', 'POST'])
def new_transaction():
    form = TransactionForm()
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        t = Transaction(amount=form.amount.data,
                        description=form.description.data,
                        date=form.date.data,
                        category_id=form.category.data or None,
                        type=form.type.data)
        db.session.add(t)
        db.session.commit()
        flash('Transaction added', 'success')
        return redirect(url_for('transaction_list'))
    return render_template('transaction_form.html', form=form, title='New Transaction')

@app.route('/transactions/<int:id>/edit', methods=['GET', 'POST'])
def edit_transaction(id):
    t = Transaction.query.get_or_404(id)
    form = TransactionForm(obj=t)
    form.category.choices = [(c.id, c.name) for c in Category.query.all()]
    if form.validate_on_submit():
        t.amount = form.amount.data
        t.description = form.description.data
        t.date = form.date.data
        t.category_id = form.category.data or None
        t.type = form.type.data
        db.session.commit()
        flash('Transaction updated', 'success')
        return redirect(url_for('transaction_list'))
    return render_template('transaction_form.html', form=form, title='Edit Transaction')

@app.route('/transactions/<int:id>/delete', methods=['POST'])
def delete_transaction(id):
    t = Transaction.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Transaction deleted', 'success')
    return redirect(url_for('transaction_list'))

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', message='Page not found'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message='An unexpected error occurred'), 500

if __name__ == '__main__':
    app.run(debug=True)
