.PHONY: install test demo clean format lint

install:
	pip install -e ".[dev]"

test:
	pytest -v --cov=mcp_knowledge_librarian --cov-report=html --cov-report=term

demo:
	@echo "Setting up demo environment..."
	@mkdir -p demo_library
	@python scripts/create_demo_pdfs.py
	@echo "\nIndexing demo documents..."
	@python scripts/demo.py index
	@echo "\nRunning demo searches..."
	@python scripts/demo.py search

clean:
	rm -rf .index/
	rm -rf demo_library/
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

format:
	black src/ tests/

lint:
	ruff check src/ tests/

help:
	@echo "Available commands:"
	@echo "  make install  - Install package and dependencies"
	@echo "  make test     - Run test suite with coverage"
	@echo "  make demo     - Run demo with sample PDFs"
	@echo "  make clean    - Clean generated files and caches"
	@echo "  make format   - Format code with black"
	@echo "  make lint     - Lint code with ruff"
