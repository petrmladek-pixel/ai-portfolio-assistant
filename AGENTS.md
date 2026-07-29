# Project Architecture Standards (python_template_uv)

You are a senior Python architect. When generating code, refactoring, or creating
new modules in this project, you MUST strictly follow the rules below.

## 1. Project Structure (Src Layout)

The project strictly uses a modern src-layout with the uv package manager.

- Source code is located exclusively in src/python_template_uv/.
- Tests are located in tests/.
- Never create application logic directly in the root directory.

## 2. Separation of Concerns

- main.py: Serves only as the entrypoint. It initializes FastAPI, defines
  middleware and CORS, and registers routers. It must not contain any business
  logic or direct integrations.
- models.py: Contains only Pydantic models for input and output validation.
- api/: Contains endpoints defined with APIRouter. Endpoints only accept
  requests, call the appropriate services through FastAPI Depends, and return
  validated data.
- services/: Contains classes responsible for integrations. These services must
  not directly depend on FastAPI HTTP objects.
- config.py: Manages settings using load_dotenv or pydantic-settings.

## 3. Code and Testing Standards

- All imports must be absolute from src.
- Use pytest and synchronous/asynchronous TestClient for testing.
- Please run the tests using uv run instead of raw pytest. Use this exact command:
  uv run pytest tests/test_market_data.py
- Tests must cover both valid flows and error states, such as empty inputs.
- Be compliant with Ruff checks. This includes a STRICT maximum line length of 88 characters for ALL lines, including comments, docstrings, and code. Never generate any line longer than 88 characters.

## 4. Development Workflow

- Manage all dependencies with uv.
- Use Ruff for static analysis and formatting.

## Commit Standards (STRICT)

Whenever you generate a commit message or create a commit, you MUST write the
commit message in English and strictly follow the Conventional Commits format:

Format: <type>(<scope>): <lowercase description without a trailing period>

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation changes
- chore: Maintenance, packages, or gitignore changes
- refactor: A code change that does not alter behavior

## Behavior Rules

1. Always ensure that sensitive keys, such as variables stored in .env, are
   never included in commits.
2. Before committing, verify that the code contains no syntax errors.
3. All code comments, docstrings, type hint descriptions, and commit messages
   MUST be written strictly in English.
