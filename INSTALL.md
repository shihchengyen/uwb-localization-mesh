# Installation Guide

## Using uv (recommended)

1. Create and activate virtual environment:
```bash
# Create venv
uv venv

# Activate
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows
```

2. Install in development mode:
```bash
# Install dependencies
uv pip install -r requirements.txt

# Install package in editable mode
uv pip install -e .
```


## Verify Installation

```bash
# Should run without import errors
uv run Server_bring_up.py
```

## Development Tools

```bash
# Run tests
uv run -m pytest

# Run linter
uv run -m ruff check .
```

## Common Issues

1. Import errors:
   - Make sure you've installed in editable mode (-e flag)
   - Verify your virtual environment is activated
   - Check PYTHONPATH includes project root

2. Build errors:
   - Try removing and recreating virtual environment
   - Update uv: `pip install -U uv`
   - Check Python version (requires >=3.8)
