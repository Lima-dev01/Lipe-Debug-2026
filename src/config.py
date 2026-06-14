import json
import os

# Caminho absoluto até settings.json (funciona de qualquer diretório)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SETTINGS_PATH = os.path.join(_BASE_DIR, "settings.json")

def load() -> dict:
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# Instância global — importe CONFIG em qualquer módulo
CONFIG = load()