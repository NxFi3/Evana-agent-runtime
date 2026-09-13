from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
import os

# Initialize Flask app
app = Flask(__name__)
# Secret key is required for session management (shopping cart)
app.secret_key = 'your_super_secret_key_for_ecommerce'

# --- Product Data Simulation ---
# Since no product data (descriptions, prices) was provided, we must simulate it 
# based on the available image filenames.
# Filename -> Product Name (derived) -> Product Details
PRODUCTS = {
    "Wireless Headphones.jpeg": {
        "name": "Wireless Headphones",
        "price": 199.99,
        "description": "Experience crystal clear audio with these comfortable and stylish wireless headphones. Perfect for travel and daily use.",
        "image_filename": "Wireless Headphones.jpeg"
    },
    "Bluetooth Speaker.jpeg": {
        "name": "Portable Bluetooth Speaker",
        "price": 79.50,
        "description": "Take your music anywhere with our rugged and powerful Bluetooth speaker. Long battery life guaranteed.",
        "image_filename": "Bluetooth Speaker.jpeg"
    },
    "4K Monitor.jpeg": {
        "name": "Ultra HD 4K Monitor",
        "price": 349.99,
        "description": "Stunning clarity and vibrant colors on this 27-inch 4K monitor. Ideal for professional design and gaming.",
        "image_filename": "4K Monitor.jpeg"
    },
    "Gaming Mouse.jpeg": {
        "name": "High-Precision Gaming Mouse",
        "price": 59.99,
        "description": "Dominate the competition with this ergonomic and ultra-responsive gaming mouse. Customizable DPI settings.",
        "image_filename": "Gaming Mouse.jpeg"
    },
    "Laptop Pro.jpeg": {
        "name": "Professional Laptop Pro",
        "price": 1299.00,
        "description": "A powerful and sleek laptop designed for professionals. Fast performance and all-day battery life.",
        "image_filename": "Laptop Pro.jpeg"
    },
    "smartphone x.jpeg": {
        "name": "Smartphone X",
        "price": 899.99,
        "description": "The latest smartphone with a brilliant display, advanced camera system, and all-day battery power.",
        "image_filename": "smartphone x.jpeg"
    }
}

# Helper function to get product info by filename (key in PRODUCTS dict)
def get_product_by_filename(filename):
    return PRODUCTS.get(filename)

# --- Routes ---

@app.route('/')
def index():
    """Product listing/home page."""
    products_list = []
    for filename, data in PRODUCTS.items():
        products_list.append({
            'filename': filename,
            'name': data['name'],
            'price': data['price'],
            'image_filename': data['image_filename']
        })
    return render_template('index.html', products=products_list)

@app.route('/product/<string:image_filename>')
def product_detail(image_filename):
    """Product detail page."""
    product = get_product_by_filename(image_filename)
    if not product:
        # If the image_filename doesn't match a known product, raise 404
        abort(404)
    
    return render_template('product_detail.html', product=product)

@app.route('/cart', methods=['GET', 'POST'])
def cart():
    """Shopping cart page."""
    # Initialize cart if it's the first time visiting
    if 'cart' not in session:
        session['cart'] = {}
    
    cart_items = session['cart']
    cart_contents = []
    total_price = 0.0
    
    # Build cart contents list for rendering
    for product_filename, details in cart_items.items():
        product_data = get_product_by_filename(product_filename)
        if product_data:
            item_total = product_data['price'] * details['quantity']
            total_price += item_total
            cart_contents.append({
                'product_filename': product_filename,
                'name': product_data['name'],
                'price': product_data['price'],
                'quantity': details['quantity'],
                'item_total': item_total,
                'image_filename': product_data['image_filename']
            })

    return render_template('cart.html', cart_items=cart_contents, total_price=total_price)

@app.route('/add_to_cart/<string:image_filename>', methods=['POST'])
def add_to_cart(image_filename):
    """Adds a product to the cart."""
    product = get_product_by_filename(image_filename)
    if not product:
        flash('Error: Product not found.', 'error')
        return redirect(url_for('index'))

    quantity = 1 # Simple implementation: always add 1
    
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    
    if image_filename in cart:
        cart[image_filename]['quantity'] += quantity
    else:
        cart[image_filename] = {'quantity': quantity}
    
    flash(f'{product["name"]} added to cart!', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout')
def checkout():
    """Simulated checkout page."""
    if not session.get('cart'):
        flash('Your cart is empty!', 'error')
        return redirect(url_for('index'))
    
    # Clear cart after simulated checkout
    session['cart'] = {}
    flash('✅ Order placed successfully! Thank you for shopping with us.', 'success')
    return redirect(url_for('index'))


# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(error):
    """Custom 404 page handler."""
    return render_template('404.html'), 404

if __name__ == '__main__':
    # Ensure the template and static directories exist before running
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Run the app without debug=True for deployment best practices
    print("--- Starting Flask Application ---")
    print("Visit http://127.0.0.1:5000/")
    app.run(debug=False) # Running without debug for better practice in automated environments

# The Flask app structure is complete. Now we need to create the templates and static assets.
