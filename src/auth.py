import bcrypt
from flask_jwt_extended import create_access_token
from src.db.models import User
# get_db will be imported and used in app.py where the Flask request context is available

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_user_token(user: User) -> str:
    """Creates an access token for a given user."""
    access_token = create_access_token(identity=user.id)
    return access_token
