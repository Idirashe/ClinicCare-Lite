"""
app.py

Entry point for ClinicCare-Lite. Run with:
    python app.py

This wires together the auth and main route blueprints. Each team
member's feature work should live in its own file under backend/,
and get registered here (or in its own blueprint) as it's built.
"""
from flask import Flask
from backend.auth.routes import auth_bp
from backend.routes.main import routes_bp


def create_app():
    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )
    # TODO (Member 1): move this to an environment variable before deployment
    # — never commit a real secret key to GitHub.
    app.secret_key = "dev-secret-key-change-me"

    app.register_blueprint(auth_bp)
    app.register_blueprint(routes_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
