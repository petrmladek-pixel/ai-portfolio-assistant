# Project Architecture Standards (portfolio_assistant)

You are a senior Python architect. When generating code, refactoring, or creating
new modules in this project, you MUST strictly follow the rules below.

## 1. Project Structure (Src Layout)

The project strictly uses a modern src-layout with the uv package manager.

- Source code is located exclusively in src/portfolio_assistant/.
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
- **config.py / settings:** Never hardcode configuration values, credentials,
  API endpoints, or sensitive keys. Always use `.env` files, environment
  variables, or a dedicated configuration class (e.g., Pydantic Settings).

## 3. Architecture Standards (Pragmatic Layering)

To ensure long-term maintainability, reuse, and easy navigation for AI agents,
the codebase strictly follows a pragmatic, lightweight three-tier layering:

- **Routers (HTTP Tier):** Located under `routers/` or `api/`. They handle HTTP
  routing, status codes, input/output validation, cookies, and exceptions.
  Never write raw SQL/SQLModel queries here. They must call CRUD functions or
  Services. If a Domain Exception is raised, map it to a FastAPI `HTTPException`.
- **Services (Business Tier - Optional):** Located under `services/`. Used ONLY
  for complex workflows coordinating multiple database operations, external API
  integrations, logging, and stateful logic (e.g., user registration combined with
  default portfolio creation). They must remain HTTP-agnostic (no FastAPI imports,
  no `HTTPException`). Raise custom domain exceptions inheriting from
  `DomainException`.
- **CRUD (Database Tier):** Located under `crud/`. Pure, stateless, module-level
  Python functions (no classes or interfaces). They handle database operations
  directly (select, insert, update, delete). They accept a `Session` and return
  SQLModel database models. No business logic belongs here.

## 4. Strict Code Quality, Modularity & DRY Rules

- **Zero Tolerance for Duplication (DRY):** Never copy-paste or duplicate entire
  code blocks to create parallel sync/async pathways. If a sync and async method
  share logic (e.g., file decoding, CSV parsing, data cleaning), you MUST extract
  this logic into an abstract base class (e.g., `BasePortfolioParser`) or shared
  private helper functions.
- **Scan Before Implementing:** Before writing any new helper function, parsing
  utility, or mathematical calculation, scan existing directories (such as base
  classes, utilities, or `FIO_LOCAL_MAPPINGS` in `fio_broker.py`) to ensure an
  equivalent helper or mapped symbol does not already exist.
- **Aim for Small, Modular Files:** Favor writing small, highly cohesive,
  single-purpose files. Try to keep source files under 150 lines of code wherever
  possible. Extract complex logic into smaller modules or helper functions.
- **Code Reuse over Patches:** Always prioritize refactoring existing files and
  improving the codebase structure over adding redundant, standalone methods.
- **Strict Maximum Line Length:** Every single line of code, comments, docstrings,
  and tests MUST strictly be under 88 characters (Ruff compatibility).
- **Financial Mathematics:** Always use `decimal.Decimal` (never use `float`) for
  all monetary values, share quantities, prices, and weights.
- **Async HTTP Client:** Use `httpx2` (the Pydantic-maintained successor) for all
  asynchronous and synchronous HTTP requests instead of legacy `httpx` or `aiohttp`.

## 5. Secure Data Pipeline & ISIN Resolution Rules

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

## 6. Development and Testing Workflow

- Manage all dependencies with `uv`.
- Use Ruff for static analysis and formatting.
- Please run the tests using `uv run` instead of raw pytest. Use this exact command:
  `uv run pytest tests/test_market_data.py`
- Tests must cover both valid flows and error states, such as empty inputs.
- When writing Pytest files with `AsyncMock`, do not reassign mocked async methods to
  raw Python functions. Use `mock_client.get.return_value = mock_response` and mock
  async context managers using `__aenter__.return_value`.
- **Max Attempt Limit for Debugging (STRICT):** If a test suite (`pytest`) or
  linter check (`ruff` / `mypy`) fails, you are allowed a maximum of TWO (2)
  consecutive attempts to fix the underlying issue. If your second attempt does
  not resolve the failure, you MUST immediately stop, present a clear summary
  of your findings and the current traceback, and ask the user for manual
  intervention. Do not loop recursively beyond 2 attempts.

## 7. Commit Standards (STRICT)

Whenever you generate a commit message or create a commit, you MUST write the
commit message in English and strictly follow the Conventional Commits format:

Format: <type>(<scope>): <lowercase description without a trailing period>

Types:
- feat: A new feature
- fix: A bug fix
- docs: Documentation changes
- chore: Maintenance, packages, or gitignore changes
- refactor: A code change that does not alter behavior or output

## 8. Behavior & Code Hygiene Rules

1. Always ensure that sensitive keys, such as variables stored in `.env`, are
   never included in commits.
2. Before committing, verify that the code contains no syntax errors.
3. All code comments, docstrings, type hint descriptions, and commit messages
   MUST be written strictly in English.
4. **Code Hygiene (No Czech Diacritics):** Python source files must never contain
   Czech diacritics (`[áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ]`). Define explicit exceptions
   in tests (e.g., via `EXCLUDED_FILES` in a code hygiene test) only for localized
   parsers that legitimately require parsing raw Czech CSV headers (like Fio e-Broker).
