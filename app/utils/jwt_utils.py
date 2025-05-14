import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, redirect, url_for

SECRET_KEY = 'comm_test_app123'
ALGORITHM = 'HS256'
EXPIRATION_MINUTES = 120

def generate_token(user_id, role):
    payload = {
        'sub': str(user_id),
        'role': role,
        'exp': datetime.utcnow() + timedelta(minutes=EXPIRATION_MINUTES)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        print("⚠ Token expired.")
        return None
    except jwt.InvalidTokenError as e:
        print(f"⚠ Invalid token: {e}")
        return None

def redirect_to_login(role):
    if role == 'admin':
        return redirect(url_for('admin_routes.login'))
    return redirect(url_for('student_routes.student_login'))

def jwt_required(role=None):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.cookies.get('jwt_token')
            print("🔐 Incoming token:", token)

            if not token:
                print("❌ No token found.")
                return redirect_to_login(role)

            payload = decode_token(token)
            print("📦 Decoded payload:", payload)

            if not payload:
                print("❌ Invalid or expired token.")
                return redirect_to_login(role)

            if role and payload.get('role') != role:
                print(f"❌ Role mismatch: expected '{role}' but got '{payload.get('role')}'")
                return redirect_to_login(role)

            request.user_id = payload['sub']
            request.user_role = payload['role']
            print("✅ JWT verified: user_id =", request.user_id, "| role =", request.user_role)
            return f(*args, **kwargs)
        return decorated_function
    return wrapper
