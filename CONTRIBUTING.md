# Contributing

Contributions are welcome! Whether you want to report a bug, propose a
feature, or submit code — please open an issue or pull request.

## Reporting bugs

Use the **Bug report** issue template. Include:
- Add-on version (from the HA Supervisor → BookStack RAG card)
- Home Assistant version + installation type (HassOS / Supervised / Container)
- Add-on logs (Supervisor → BookStack RAG → Log tab)
- Steps to reproduce

## Submitting code

1. Fork the repo and create a feature branch from `main`.
2. Make your change. Keep PRs focused; one logical change per PR.
3. Make sure lint and tests are green:
   ```bash
   python -m ruff check .
   python -m ruff format --check .
   python -m pytest
   ```
4. Commit with a descriptive message (what changed, *why*, trade-offs).
5. Open a pull request. The CI pipeline (lint, test, container build) will
   run on every push.

## Coding style

- Python 3.12+, full type hints, ruff-default formatting (configured in `.ruff.toml`).
- Comments only when the *why* is non-obvious — well-named identifiers should
  cover the *what*.
- Tests live in `bookstack-rag/tests/` and mirror the `bookstack-rag/app/`
  module structure.

## Code of conduct

Be civil. The project follows the
[Contributor Covenant](https://www.contributor-covenant.org/) in spirit if
not in formal text.

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](LICENSE).
