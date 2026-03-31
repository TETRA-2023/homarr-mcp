# Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Install development dependencies (`uv sync --all-extras --dev`)
4. Make your changes
5. Run tests (`uv run pytest tests/test_server.py -v`)
6. Ensure linting passes (`uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`)
7. Commit your changes using conventional commits (`git commit -m 'feat: add some amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request
