# -*- coding: utf-8 -*-

"""Načtení konfigurace a inicializace analyzátorů pro newton_one."""

import configparser
import os


from src.newton_one.models import MAX_LLM_RETRY

# Singleton cache pro inicializaci modelů jednou (Phase 4 – optimalizace API volání)
_MODEL_CACHE = {
    "ner": None,                # spaCy NER instance
    "sentiment": None,          # nlptown/bert-base-multilingual-uncased-sentiment text-classification
    "dezinformace": None,       # bart-large-mnli zero-shot classifier (WORST OFFENDER - optimized here)
}


def _get_model(model_key):
    """Vrátí singleton instanci modelu — inicializuje se pouze jednou."""
    if _MODEL_CACHE[model_key] is not None:
        return _MODEL_CACHE[model_key]

    raise RuntimeError(f"Model '{model_key}' ještě není inicializován. "
                       f"Volejte _init_{model_key}_analyzer() před použitím.")


def _check_llm_config():
    """Vrátí dict s LLM konfigurací nebo chybovou zprávu."""
    if not os.path.exists(_llm_config_path):
        return {
            "valid": False,
            "message": f"❌ Konfigurační soubor {_llm_config_path} neexistuje",
        }
    _llm_config = configparser.ConfigParser()
    _llm_config.read(_llm_config_path)
    if "LLM" not in _llm_config:
        return {
            "valid": False,
            "message": f"❌ V konfiguračním souboru chybí sekce [LLM]",
        }
    return {
        "valid": True,
        "host": _llm_config["LLM"]["host"],
        "port": int(_llm_config["LLM"]["port"]),
        "model": _llm_config["LLM"]["model"],
        "temperature": float(_llm_config["LLM"]["temperature"]),
        "max_tokens": int(_llm_config["LLM"]["max_tokens"]),
    }


# Konfigurace Phase 4 – optimalizace API volání
try:
    from config_loader import ConfigLoader
    _cfg = ConfigLoader()
except ImportError:
    _cfg = None

if _cfg is not None:
    try:
        _BATCH_SIZE = int(_cfg.get_int("newton_one", "batch_size", fallback=50))
    except (ValueError, TypeError):
        _BATCH_SIZE = 50
else:
    _BATCH_SIZE = 50


# Konfigurace LLM endpointu (Phase 5 – analýza pomocí lokálního LLM)
_llm_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../config.ini")
