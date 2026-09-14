# EvanaEval/app/routes.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from . import db
from .models import Category, Transaction
from .forms import CategoryForm, TransactionForm
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/dashboard')
def dashboard():
    # Get filter parameters
    category_id = request.args.get('category', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Base query
    query = Transaction.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date >= start)
        except ValueError:
            flash('Invalid start date format', 'danger')
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            query = query.filter(Transaction.date <= end)
        except ValueError:
            flash('Invalid end date format', 'danger')

    transactions = query.order_by(Transaction.date.desc()).all()

    # Totals
    income = sum(t.amount for t in transactions if t.amount > 0)
    expenses = sum(t.amount for t in transactions if t.amount < 0)
    balance = income + expenses

    categories = Category.query.all()
    return render_template('dashboard.html', transactions=transactions, income=income,
                           expenses=expenses, balance=balance, categories=categories,
                           selected_category=category_id, start_date=start_date,
                           end_date=end_date)

@bp.route('/transactions/add', methods=['GET', 'POST'])
def add_transaction():
    form = TransactionForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by('name')]
    if form.validate_on_submit():
        t = Transaction(description=form.description.data,
                        amount=form.amount.data,
                        date=form.date.data,
                        category_id=form.category_id.data)
        db.session.add(t)
        db.session.commit()
        flash('Transaction added', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('transaction_form.html', form=form, title='Add Transaction')

@bp.route('/transactions/edit/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    t = Transaction.query.get_or_404(id)
    form = TransactionForm(obj=t)
    form.category_id.choices = [(c.id, c.name) for c in Category.query.order_by('name')]
    if form.validate_on_submit():
        t.description = form.description.data
        t.amount = form.amount.data
        t.date = form.date.data
        t.category_id = form.category_id.data
        db.session.commit()
        flash('Transaction updated', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('transaction_form.html', form=form, title='Edit Transaction')

@bp.route('/transactions/delete/<int:id>', methods=['POST'])
def delete_transaction(id):
    t = Transaction.query.get_or_404(id)
    db.session.delete(t)
    db.session.commit()
    flash('Transaction deleted', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/categories')
def list_categories():
    categories = Category.query.order_by('name').all()
    return render_template('categories.html', categories=categories)

@bp.route('/categories/add', methods=['GET', 'POST'])
def add_category():
    form = CategoryForm()
    if form.validate_on_submit():
        c = Category(name=form.name.data)
        db.session.add(c)
        try:
            db.session.commit()
            flash('Category added', 'success')
            return redirect(url_for('main.list_categories'))
        except Exception:
            db.session.rollback()
            flash('Category name must be unique', 'danger')
    return render_template('category_form.html', form=form, title='Add Category')

@bp.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
def edit_category(id):
    c = Category.query.get_or_404(id)
    form = CategoryForm(obj=c)
    if form.validate_on_submit():
        c.name = form.name.data
        try:
            db.session.commit()
            flash('Category updated', 'success')
            return redirect(url_for('main.list_categories'))
        except Exception:
            db.session.rollback()
            flash('Category name must be unique', 'danger')
    return render_template('category_form.html', form=form, title='Edit Category')

@bp.route('/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    c = Category.query.get_or_404(id)
    if c.transactions:
        flash('Cannot delete category with transactions', 'danger')
        return redirect(url_for('main.list_categories'))
    db.session.delete(c)
    db.session.commit()
    flash('Category deleted', 'success')
    return redirect(url_for('main.list_categories'))

# Register blueprint in app factory
from . import create_app

# The blueprint will be registered in create_app
