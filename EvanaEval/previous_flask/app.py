from flask import Flask, jsonify, render_template_string
import sqlite3
import os

app = Flask(__name__)

# Ensure database exists
DB_PATH = os.path.join(app.root_path, 'app.db')

if not os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE IF NOT EXISTS dummy (id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    html = """
    <html>
        <head><title>Home</title></head>
        <body>
            <h1>Welcome to the Flask App</h1>
        </body>
    </html>
    """
    return render_template_string(html)

@app.route('/health')
def health():
    return jsonify(status="ok")

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000)
