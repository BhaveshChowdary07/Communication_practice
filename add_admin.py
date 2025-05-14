from app import app, db
from app.models import Admin
from werkzeug.security import generate_password_hash

with app.app_context():
    email = "ankurah777@gmail.com"
    raw_password = "admin123"
    existing = Admin.query.filter_by(email=email).first()

    if existing:
        print("⚠️ Admin already exists.")
    else:
        admin = Admin(email=email, password=generate_password_hash(raw_password))
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin added. Email: {email}, Password: {raw_password}")
