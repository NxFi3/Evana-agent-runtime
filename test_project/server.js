const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3002;

app.use(cors());
app.use(bodyParser.json());
app.use(express.static(path.join(__dirname, 'public')));

// In-memory data
let products = [
  { id: 1, name: 'Laptop', description: 'High performance laptop', price: 999.99, image: 'https://via.placeholder.com/200?text=Laptop' },
  { id: 2, name: 'Headphones', description: 'Noise cancelling headphones', price: 199.99, image: 'https://via.placeholder.com/200?text=Headphones' },
  { id: 3, name: 'Smartphone', description: 'Latest model smartphone', price: 799.99, image: 'https://via.placeholder.com/200?text=Smartphone' }
];
let cart = [];

// API endpoints
app.get('/api/products', (req, res) => {
  res.json(products);
});

app.get('/api/products/:id', (req, res) => {
  const id = parseInt(req.params.id);
  const product = products.find(p => p.id === id);
  if (product) {
    res.json(product);
  } else {
    res.status(404).json({ error: 'Product not found' });
  }
});

app.post('/api/cart', (req, res) => {
  const { productId, quantity } = req.body;
  const product = products.find(p => p.id === productId);
  if (!product) {
    return res.status(404).json({ error: 'Product not found' });
  }
  const existing = cart.find(item => item.productId === productId);
  if (existing) {
    existing.quantity += quantity;
  } else {
    cart.push({ productId, quantity });
  }
  const detailedCart = cart.map(item => {
    const prod = products.find(p => p.id === item.productId);
    return { productId: item.productId, quantity: item.quantity, product: prod };
  });
  res.json({ message: 'Added to cart', cart: detailedCart });
});

app.get('/api/cart', (req, res) => {
  const detailedCart = cart.map(item => {
    const product = products.find(p => p.id === item.productId);
    return {
      productId: item.productId,
      quantity: item.quantity,
      product
    };
  });
  res.json(detailedCart);
});

app.delete('/api/cart/:productId', (req, res) => {
  const productId = parseInt(req.params.productId);
  cart = cart.filter(item => item.productId !== productId);
  res.json({ message: 'Item removed', cart });
});

app.post('/api/checkout', (req, res) => {
  // Simple checkout: clear cart and return receipt
  const receipt = {
    items: cart.map(item => {
      const product = products.find(p => p.id === item.productId);
      return {
        productId: item.productId,
        name: product.name,
        quantity: item.quantity,
        price: product.price,
        total: product.price * item.quantity
      };
    }),
    total: cart.reduce((sum, item) => {
      const product = products.find(p => p.id === item.productId);
      return sum + product.price * item.quantity;
    }, 0)
  };
  cart = [];
  res.json({ message: 'Checkout successful', receipt });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
