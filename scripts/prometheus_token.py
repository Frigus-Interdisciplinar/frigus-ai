"""Grava o API_KEYS__METRICS_TOKEN do .env no arquivo que o Prometheus do compose lê (`credentials_file`)."""

from pathlib import Path

from dotenv import dotenv_values

token = dotenv_values(".env").get("API_KEYS__METRICS_TOKEN") or ""
Path("observability/prometheus/metrics_token").write_text(token, encoding="utf-8")
