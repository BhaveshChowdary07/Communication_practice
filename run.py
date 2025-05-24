from app import app

if __name__ == '__main__':
    app.run(debug=True)

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 15,
    'max_overflow': 20,
    'pool_timeout': 30,
    'pool_recycle': 900,
    'pool_pre_ping': True
}
