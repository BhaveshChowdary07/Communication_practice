from flask import Flask, render_template 
from flask_sqlalchemy import SQLAlchemy
from config import Config
import base64

# --- Initialize Flask App ---
app = Flask(__name__)
app.config.from_object(Config)

# ✅ Add database connection resiliency
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,   # Fixes stale connection issues
    'pool_recycle': 1800     # Recycle connections every 30 minutes
}

# --- Initialize SQLAlchemy ---
db = SQLAlchemy(app)

# --- Register Blueprints ---
from app.routes import admin_routes, student_routes
app.register_blueprint(admin_routes.bp)
app.register_blueprint(student_routes.bp)

# --- Jinja2 Filters ---
app.jinja_env.filters['b64encode'] = lambda data: base64.b64encode(data).decode('utf-8') if data else ''

# --- Auto-create Tables (Optional, useful for dev only) ---
with app.app_context():
    db.create_all()

# --- Home Route ---
@app.route('/')
def home():
    return render_template('home.html')
