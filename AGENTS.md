# Project Architecture Standards (python_template_uv)

You are a senior Python architect. When generating code, refactoring, or creating
new modules in this project, you MUST strictly follow the rules below.

## 1. Project Structure (Src Layout)

The project strictly uses a modern src-layout with the uv package manager.

- Source code is located exclusively in src/python_template_uv/.
- Tests are located in tests/.
- Never create application logic directly in the root directory.

## 2. Separation of Concerns & Clean Code

- **main.py:** Serves only as the entrypoint. It initializes FastAPI, defines
  middleware and CORS, and registers routers. It must not contain any business
  logic or direct integrations.
- **models.py:** Contains only Pydantic V2 models for input and output validation.
- **api/:** Contains endpoints defined with `APIRouter`. Endpoints only accept
  requests, call services through FastAPI `Depends`, and return validated data.
- **services/:** Contains classes responsible for integrations. These services must
  not directly depend on FastAPI HTTP objects.
- **config.py:** Manages settings using load_dotenv or pydantic-settings.

## 3. Strict Code Quality & DRY Refactoring Rules

- **Zero Tolerance for Duplication (DRY):** Never copy-paste or duplicate entire
  code blocks to create parallel sync/async pathways. If a sync and async method
  share logic (e.g., file decoding, CSV parsing, data cleaning), you MUST extract
  this logic into an abstract base class (e.g., `BasePortfolioParser`) or shared
  private helper functions.
- **Code Reuse over Patches:** Always prioritize refactoring existing files and
  improving the codebase structure over adding redundant, standalone methods.
- **Strict Maximum Line Length:** Every single line of code, comments, docstrings,
  and tests MUST strictly be under 88 characters (Ruff compatibility).
- **Financial Mathematics:** Always use `decimal.Decimal` (never use `float`) for
  all monetary values, share quantities, prices, and weights.
- **Async HTTP Client:** Use `httpx2` (the Pydantic-maintained successor) for all
  asynchronous and synchronous HTTP requests instead of legacy `httpx` or `aiohttp`.

## 4. Secure Data Pipeline & ISIN Resolution Rules

- **No Hardcoded Data Fallbacks:** Never keep or maintain static fallback
  dictionaries (like `ISIN_TO_TICKER` inside parsers) if a dynamic resolver
  service is available.
- **Exact-Match Round-Trip Validation:** When resolving identifiers (such as ISINs
  via Yahoo Search API), you must strictly verify that the returned item's metadata
  exactly matches the queried identifier. Do not accept partial or fuzzy matches.
- **First-Class Unknowns:** If an identifier cannot be resolved, fail closed. Map the
  position ticker to `"UNKNOWN"`, assign a descriptive placeholder name (e.g.,
  `"Unknown Asset (ISIN: {isin})"`), and set all its financial/valuation amounts to
  `Decimal("0.00")`. Never let raw, unresolved identifiers flow downstream.

## 5. Development and Testing Workflow

- Manage all dependencies with `uv`.
- Use Ruff for static analysis and formatting.
- Please run the tests using `uv run` instead of raw pytest. Use this exact command:
  `uv run pytest tests/test_market_data.py`
- Tests must cover both valid flows and error states, such as empty inputs.
- When writing Pytest files with `AsyncMock`, do not reassign mocked async methods to
  raw Python functions. Use `mock_client.get.return_value = mock_response` and mock
  async context managers using `__aenter__.return_value`.

## 6. Commit Standards (STRICT)

Whenever you generate a commit message or create a commit, you MUST write the
commit message in English and strictly follow the Conventional Commits format:

Format: <type>(<scope>): <lowercase description without a trailing period>

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation changes
- chore: Maintenance, packages, or gitignore changes
- refactor: A code change that does not alter behavior or output

## 7. Behavior & Code Hygiene Rules

1. Always ensure that sensitive keys, such as variables stored in `.env`, are
   never included in commits.
2. Before committing, verify that the code contains no syntax errors.
3. All code comments, docstrings, type hint descriptions, and commit messages
   MUST be written strictly in English.
4. **Code Hygiene (No Czech Diacritics):** Python source files must never contain
   Czech diacritics (`[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]`). Define explicit exceptions
   in tests (e.g., via `EXCLUDED_FILES` in a code hygiene test) only for localized
   parsers that legitimately require parsing raw Czech CSV headers (like Fio e-Broker).
