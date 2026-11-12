"""ACEest Fitness & Gym - Flask entrypoint.

    python ACEest_Fitness.py              # local development server
    gunicorn ACEest_Fitness:app           # how the container runs it
"""

from __future__ import annotations

import os

from aceest import create_app

app = create_app()


if __name__ == "__main__":  # pragma: no cover - dev server only
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_ENV") == "development",
    )
