document.addEventListener('DOMContentLoaded', () => {
  const productList = document.getElementById('product-list');
  const cartCount = document.getElementById('cart-count');
  const cartSection = document.getElementById('cart');
  const cartItemsDiv = document.getElementById('cart-items');
  const checkoutBtn = document.getElementById('checkout-btn');

  let cart = [];

  // Fetch products
  fetch('/api/products')
    .then(r => r.json())
    .then(products => {
      products.forEach(p => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
          <img src="${p.image}" alt="${p.name}">
          <h3>${p.name}</h3>
          <p>${p.description}</p>
          <p>Price: $${p.price.toFixed(2)}</p>
          <button data-id="${p.id}">Add to Cart</button>
        `;
        productList.appendChild(card);
      });
    });

  // Add to cart handler
  productList.addEventListener('click', e => {
    if (e.target.tagName === 'BUTTON') {
      const id = parseInt(e.target.dataset.id);
      fetch('/api/cart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId: id, quantity: 1 })
      })
        .then(r => r.json())
        .then(res => {
          cart = res.cart;
          cartCount.textContent = cart.reduce((s, i) => s + i.quantity, 0);
        });
    }
  });

  // Show cart section when cart link clicked
  document.querySelector('a[href="#cart"]').addEventListener('click', e => {
    e.preventDefault();
    cartSection.style.display = 'block';
    renderCart();
  });

  function renderCart() {
    cartItemsDiv.innerHTML = '';
    if (cart.length === 0) {
      cartItemsDiv.textContent = 'Cart is empty';
      return;
    }
    cart.forEach(item => {
      const div = document.createElement('div');
      div.className = 'cart-item';
      div.innerHTML = `
        <span>${item.product.name} (x${item.quantity}) - $${(item.product.price * item.quantity).toFixed(2)}</span>
        <button data-id="${item.productId}">Remove</button>
      `;
      cartItemsDiv.appendChild(div);
    });
  }

  // Remove from cart
  cartItemsDiv.addEventListener('click', e => {
    if (e.target.tagName === 'BUTTON') {
      const id = parseInt(e.target.dataset.id);
      fetch(`/api/cart/${id}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(res => {
          cart = res.cart;
          cartCount.textContent = cart.reduce((s, i) => s + i.quantity, 0);
          renderCart();
        });
    }
  });

  // Checkout
  checkoutBtn.addEventListener('click', () => {
    fetch('/api/checkout', { method: 'POST' })
      .then(r => r.json())
      .then(res => {
        alert('Checkout successful! Total: $' + res.receipt.total.toFixed(2));
        cart = [];
        cartCount.textContent = 0;
        renderCart();
      });
  });
});
