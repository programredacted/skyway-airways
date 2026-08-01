"""Local entrypoint: `py run.py` — the one command to run this project.

create_app() creates the schema and seeds it on first run, so there is no
separate migrate/seed step to remember. In production Render runs gunicorn
against the same factory (see Procfile); this file is only for local use.
"""

import os

from app import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    print(f"Skyway Airways departing from http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=True)
