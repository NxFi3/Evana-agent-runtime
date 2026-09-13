import pytest
from app import app

@pytest.fixture
def client():
    app.testing = True
    with app.test_client() as client:
        yield client

def test_index(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b"Featured Products" in response.data

def test_product_detail(client):
    # Use known product
    response = client.get('/product/Wireless%20Headphones.jpeg')
    assert response.status_code == 200
    assert b"Wireless Headphones" in response.data

def test_add_to_cart_and_checkout(client):
    # Add product
    response = client.post('/add_to_cart/Wireless%20Headphones.jpeg', follow_redirects=True)
    assert response.status_code == 200
    assert b"added to cart" in response.data.lower()

    # View cart
    response = client.get('/cart')
    assert response.status_code == 200
    assert b"Wireless Headphones" in response.data

    # Checkout
    response = client.get('/checkout', follow_redirects=True)
    assert response.status_code == 200
    assert b"order placed successfully" in response.data.lower()

# Test unknown product returns 404
def test_unknown_product(client):
    response = client.get('/product/nonexistent.jpeg')
    assert response.status_code == 404
    assert b"404" in response.data
