"""Flask app entry point."""
from __future__ import annotations

from flask import Flask

from src.api.routes import api_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return {
            "service": "ecommerce-data-platform",
            "endpoints": [
                "/api/health",
                "/api/metrics/revenue",
                "/api/metrics/revenue/monthly",
                "/api/categories/revenue",
                "/api/channels/revenue",
                "/api/products/top?limit=10",
                "/api/customers/top?limit=10",
                "/api/customers/<customer_id>/orders",
                "/api/cache/clear  (POST)",
            ],
        }

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001, debug=False)
