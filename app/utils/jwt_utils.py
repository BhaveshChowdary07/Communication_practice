from functools import wraps
from flask import request, redirect, url_for
import jwt
from datetime import datetime, timedelta

# Load keys
with open("keys/private.pem", "r") as f:
    PRIVATE_KEY = f.read()

with open("keys/public.pem", "r") as f:
    PUBLIC_KEY = f.read()

ALGORITHM = 'RS256'
ACCESS_EXPIRY_MINUTES = 60
REFRESH_EXPIRY_HOURS = 12


def generate_access_token(user_id, role):
    payload = {
        'sub': str(user_id),
        'role': role,
        'type': 'access',
        'exp': datetime.utcnow() + timedelta(minutes=ACCESS_EXPIRY_MINUTES)
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)


def generate_refresh_token(user_id):
    payload = {
        'sub': str(user_id),
        'type': 'refresh',
        'exp': datetime.utcnow() + timedelta(hours=REFRESH_EXPIRY_HOURS)
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm=ALGORITHM)


def decode_token(token):
    try:
        return jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def redirect_to_login(role):
    if role == 'admin':
        return redirect(url_for('admin_routes.login'))
    return redirect(url_for('student_routes.student_login'))


def jwt_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = None

            # ✅ Try Authorization header first
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
            else:
                # Fallback to cookies
                token = request.cookies.get('jwt_token')

            if not token:
                return redirect_to_login(role)

            payload = decode_token(token)
            if not payload:
                return redirect_to_login(role)

            if role and payload.get('role') != role:
                return redirect_to_login(role)

            request.user_id = payload['sub']
            request.user_role = payload['role']
            return f(*args, **kwargs)
        return decorated_function
    return wrapper
