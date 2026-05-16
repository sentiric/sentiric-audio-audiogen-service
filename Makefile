.PHONY: setup clean dev-up dev-down dev-logs

VENV = .venv
UV = uv

setup:
	@echo "🚀 Setting up virtual environment with uv..."
	$(UV) venv $(VENV)
	$(UV) pip install -r requirements.txt

clean:
	rm -rf .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +

# --- LOCAL DEV ENVIRONMENT ---
dev-up:
	@echo "🔥 Starting isolated local environment..."
	docker compose up --build -d

dev-logs:
	@echo "📋 Tailing logs..."
	docker compose logs -f audio-audiogen-service

dev-down:
	@echo "🛑 Shutting down local environment..."
	docker compose down -v