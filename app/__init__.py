from flask import Flask
from app.config import Config


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    from app.routes.operador import operador_bp
    from app.routes.analista import analista_bp
    from app.routes.api import api_bp

    flask_app.register_blueprint(operador_bp)
    flask_app.register_blueprint(analista_bp)
    flask_app.register_blueprint(api_bp, url_prefix="/api")

    return flask_app
