# EvanaEval/tests/test_app.py
import os
import pytest
import sys
sys.path.append('..')
from EvanaEval.app import app, db, Category, Transaction
from datetime import date

@pytest.fixture
def client():
    # Configure app for testing
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            # Add categories
            for name in ['Income', 'Food', 'Rent']:
                db.session.add(Category(name=name))
            db.session.commit()
        yield client

def test_add_transaction(client):
    # Get category id
    with app.app_context():
        cat = Category.query.filter_by(name='Income').first()
        cat_id = cat.id
    response = client.post('/add', data={
        'amount': '1000',
        'date': '2023-01-01',
        'category': str(cat_id),
        'description': 'Salary'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Transaction added' in response.data
    with app.app_context():
        t = Transaction.query.filter_by(description='Salary').first()
        assert t is not None
        assert t.amount == 1000

def test_edit_transaction(client):
    with app.app_context():
        cat = Category.query.filter_by(name='Income').first()
        t = Transaction(amount=500, date=date(2023,1,2), category_id=cat.id, description='Bonus')
        db.session.add(t)
        db.session.commit()
        tid = t.id
    response = client.post(f'/edit/{tid}', data={
        'amount': '600',
        'date': '2023-01-03',
        'category': str(cat.id),
        'description': 'Updated Bonus'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Transaction updated' in response.data
    with app.app_context():
        t = Transaction.query.get(tid)
        assert t.amount == 600
        assert t.description == 'Updated Bonus'

def test_delete_transaction(client):
    with app.app_context():
        cat = Category.query.filter_by(name='Income').first()
        t = Transaction(amount=200, date=date(2023,1,4), category_id=cat.id, description='Gift')
        db.session.add(t)
        db.session.commit()
        tid = t.id
    response = client.post(f'/delete/{tid}', follow_redirects=True)
    assert response.status_code == 200
    assert b'Transaction deleted' in response.data
    with app.app_context():
        t = Transaction.query.get(tid)
        assert t is None

def test_dashboard_totals(client):
    with app.app_context():
        cat_income = Category.query.filter_by(name='Income').first()
        cat_food = Category.query.filter_by(name='Food').first()
        db.session.add_all([
            Transaction(amount=1000, date=date(2023,1,1), category_id=cat_income.id, description='Salary'),
            Transaction(amount=-200, date=date(2023,1,2), category_id=cat_food.id, description='Groceries')
        ])
        db.session.commit()
    response = client.get('/')
    assert response.status_code == 200
    assert b'Income: $1000' in response.data
    assert b'Expenses: $200' in response.data
    assert b'Balance: $800' in response.data

# Test filtering
def test_filter_transactions(client):
    with app.app_context():
        cat_income = Category.query.filter_by(name='Income').first()
        cat_food = Category.query.filter_by(name='Food').first()
        db.session.add_all([
            Transaction(amount=500, date=date(2023,1,5), category_id=cat_income.id, description='Freelance'),
            Transaction(amount=-50, date=date(2023,1,6), category_id=cat_food.id, description='Snack')
        ])
        db.session.commit()
    response = client.get('/filter?category={}'.format(cat_food.id))
    assert response.status_code == 200
    assert b'Snack' in response.data
    assert b'Freelance' not in response.data

