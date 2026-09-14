from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# Initialize extensions

db = SQLAlchemy()
csrf = CSRFProtect()

# Application factory

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config_name)
    db.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        from . import routes
        db.create_all()

    return app
