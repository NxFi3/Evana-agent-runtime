from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__, static_folder='product_images')
app.secret_key = 'super-secret-key-123456'

# Load local product images if available
import os

# Helper to map product id to local image filename
image_dir = os.path.join(os.path.dirname(__file__), 'product_images')
image_files = {os.path.splitext(f)[0]: f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))}

# Sample product data
products = [
    {
        'id': 1,
        'name': 'Smartphone X',
        'category': 'Phones',
        'price': 699,
        'image': image_files.get('1', 'https://images.unsplash.com/photo-1580281653784-6c7b3c6b7f5d?auto=format&fit=crop&w=400&q=80')
    },
    {
        'id': 2,
        'name': 'Laptop Pro',
        'category': 'Computers',
        'price': 1299,
        'image': image_files.get('2', 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=400&q=80')
    },
    {
        'id': 3,
        'name': 'Wireless Headphones',
        'category': 'Audio',
        'price': 199,
        'image': image_files.get('3', 'https://images.unsplash.com/photo-1516393447469-5d9b2d1b3b45?auto=format&fit=crop&w=400&q=80')
    },
    {
        'id': 4,
        'name': 'Gaming Mouse', 'category': 'Accessories', 'price': 49,
        'image': image_files.get('4', 'https://images.unsplash.com/photo-1526374875794-8f8f2c1b1b5a?auto=format&fit=crop&w=400&q=80')
    },
    {
        'id': 5,
        'name': '4K Monitor', 'category': 'Computers', 'price': 399,
        'image': image_files.get('5', 'https://images.unsplash.com/photo-1581092337487-6e5b2f0f3c7e?auto=format&fit=crop&w=400&q=80')
    },
    {
        'id': 6,
        'name': 'Bluetooth Speaker', 'category': 'Audio', 'price': 129,
        'image': image_files.get('6', 'https://images.unsplash.com/photo-1552075179-1a5c5e1d0c7c?auto=format&fit=crop&w=400&q=80')
    }
]

# Helper functions

def get_product(product_id):
    return next((p for p in products if p['id'] == product_id), None)

@app.route('/')
@app.route('/products')
def product_list():
    q = request.args.get('q', '').lower()
    category = request.args.get('category', '').lower()
    filtered = products
    if q:
        filtered = [p for p in filtered if q in p['name'].lower()]
    if category:
        filtered = [p for p in filtered if p['category'].lower() == category]
    categories = sorted(set(p['category'] for p in products))
    return render_template('index.html', products=filtered, categories=categories, query=q, selected_category=category)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = get_product(product_id)
    if not product:
        return "Product not found", 404
    return render_template('product.html', product=product)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = int(request.form.get('product_id'))
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    items = []
    total = 0
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        prod = get_product(pid)
        if prod:
            subtotal = prod['price'] * qty
            total += subtotal
            items.append({'product': prod, 'quantity': qty, 'subtotal': subtotal})
    return render_template('cart.html', items=items, total=total)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    cart = session.get('cart', {})
    for pid_str in list(cart.keys()):
        qty = int(request.form.get(f'qty_{pid_str}', 0))
        if qty <= 0:
            cart.pop(pid_str)
        else:
            cart[pid_str] = qty
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    return redirect(url_for('cart'))

if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)
