from app import app, db
from app.models import User
from werkzeug.security import generate_password_hash

with app.app_context():
    email = "bhavesh.chowdary@redsage.global"
    raw_password = "admin123"
    existing = User.query.filter_by(email=email, role='admin').first()

    if existing:
        print("⚠️ Admin already exists.")
    else:
        admin = User(email=email, password=generate_password_hash(raw_password), role='admin')
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin added. Email: {email}, Password: {raw_password}")
