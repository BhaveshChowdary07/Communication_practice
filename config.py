import os
import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_secret_key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email settings for Flask-Mail (example for Gmail SMTP)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'sreebhavesh7@gmail.com'         # Replace with admin sender email
    MAIL_PASSWORD = 'dwabbxayjojtnaho'          # Replace with app password
    MAIL_DEFAULT_SENDER = 'sreebhavesh7@gmail.com'
