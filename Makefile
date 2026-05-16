.PHONY: setup clean
VENV = .venv
UV = uv
setup:
	@echo "🚀 Setting up virtual environment with uv..."
	$(UV) venv $(VENV)
	$(UV) pip install -r requirements.txt
clean:
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
