class Config:
    """Base configuration."""
    SECRET_KEY = 'dev'  # In production use os.urandom or env var
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
