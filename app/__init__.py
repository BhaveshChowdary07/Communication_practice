from flask import Flask, render_template 
from flask_sqlalchemy import SQLAlchemy
from config import Config

# --- Initialize extensions ---
app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

# --- Register Blueprints ---
from app.routes import admin_routes, student_routes
app.register_blueprint(admin_routes.bp)
app.register_blueprint(student_routes.bp)

import base64
app.jinja_env.filters['b64encode'] = lambda data: base64.b64encode(data).decode('utf-8') if data else ''

@app.route('/')
def home():
    return render_template('home.html')
