# SQL Agent Assistant

A Flask-based natural-language assistant for querying a sales database with local Ollama models. The project also includes LangGraph workflow code and small tool integrations for weather, news, and dictionary lookups.

## Features

- Ask natural-language questions through a Flask web interface.
- Generate and execute SQL through the LangGraph workflow.
- Use a local `llama3.1:8b` model through Ollama.
- Query SQLite by default, or configure another SQLAlchemy-compatible database with `DATABASE_URL`.
- Explore supporting notebooks and agent modules in the repository.

## Requirements

- Python 3.10 or newer
- Ollama with the `llama3.1:8b` model
- A generated SQLite database at `database/sales.db` for the SQL workflow

Install and prepare the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Install and start the local model:

```powershell
ollama pull llama3.1:8b
ollama serve
```

## Database setup

The default database path is `database/sales.db`.

```powershell
python database\create_database.py
```

If you use the SQLAlchemy helpers in `utils/db_connection.py`, you can point the application at another database by setting `DATABASE_URL` in a local `.env` file. Do not commit credentials or `.env` files.

## Run the applications

Run the general assistant:

```powershell
python app.py
```

Run the SQL workflow interface:

```powershell
python app2.py
```

Open the address printed by Flask, usually `http://127.0.0.1:5000`.

## Project structure

```text
agents/       Agent implementations
database/     Database schema and setup scripts
graph/        LangGraph SQL workflow
llm/          Ollama chatbot and SQL generation
prompts/      System and SQL prompts
templates/    Flask HTML templates
tools/        Weather, news, and dictionary tools
utils/        Database helpers
```

## Docker

The included `Dockerfile` runs the Flask application on port 5000:

```powershell
docker build -t sql-agent-assistant .
docker run --rm -p 5000:5000 sql-agent-assistant
```

The Ollama service and model must be available to the container separately.

## Notes

- Generated SQL should be reviewed before using this project with production data.
- Keep API keys, database URLs, local model files, virtual environments, and generated databases out of version control.