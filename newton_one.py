# -*- coding: utf-8 -*-

"""
Název: newton_one.py
Popis: CLI utilita pro načtení NewtonOne CSV souboru a konverzi do JSONL formátu pro následnou analýzu.

použití:
--------
    python newton_one.py -c <cesta_k_CSV> -o <cesta_k_JSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -c, --csv   - cesta k semicolon-delimited CSV souboru (povinné)
- -o, --output - výstupní JSONL soubor (povinný)

Autor: Pavel Šenovský
Datum: 2026-08-14
"""

import argparse                                              # argumenty příkazového řádku
import os                                                     # operace se systémem

# Import analyzátorů malých modelů (Phase 3)
from config_loader import ConfigLoader                        # čtení config.ini

# NER a Sentiment imports – Phase 4: commented out, kept for reference only
try:
    from src.ner_spacy import ner_spacy                       # NER via spaCy (commented out - Phase 4 focus: dezinformace)
except ImportError:
    ner_spacy = None                                          # type: ignore

try:
    from src.sentiment_BERT_multi import sentiment_BERT_multi  # Sentiment via BERT multi-lang
except ImportError:
    sentiment_BERT_multi = None                               # type: ignore

from transformers.pipelines import pipeline as hf_pipeline     # Disinformation detection — OPTIMIZED in Phase 4


# =============================================================================
# Model cache – singleton pattern (Phase 4)
# =============================================================================

try:
    from src.newton_one.config_loader import _MODEL_CACHE, _get_model, _check_llm_config
except ImportError as e:
    print(f"❌ Chyba importu z config_loader: {e}")
    raise


# =============================================================================
# Funkce – data I/O (Phase 1-2)
# =============================================================================

from src.newton_one.data_io import nacti_csv, pretvorit_radku, ulozit_jsonl


# =============================================================================
# Konfigurace LLM endpointu (Phase 5 – analýza pomocí lokálního LLM)
# =============================================================================

_llm_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.ini")


def _check_llm_config():
    """Vrátí dict s LLM konfigurací nebo chybovou zprávu."""
    if not os.path.exists(_llm_config_path):
        return {
            "valid": False,
            "message": f"❌ Konfigurační soubor {_llm_config_path} neexistuje",
        }
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


# Maximum retry count pro LLM API volání (Phase 5)
MAX_LLM_RETRY = 3

# Konfigurace Phase 4 – optimalizace API volání
try:
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


# =============================================================================
# Konstanty — import z src/newton_one/models.py (Phase 2 – reorganizace)
# =============================================================================

from src.newton_one.models import (
    CSV_SEP,
    ENCODING,
    JSONL_ENCODING,
    OUTPUT_DELIMITER,
    SLoupce,
    UNICODE_WHITESPACE,
)


# Unicode znaky, které by mohly být mezernatami v číslech (např. U+00A0 nbsp, U+2007 thin space)


# =============================================================================
# Funkce pro analýzu malými modely (Phase 3 – NER_SM, Sentiment_SM, Dezinformace)
# =============================================================================

def _detect_jazyk_zeme(zeme):
    """
    Určí jazyk na základě sloupce Země.

    Parameters
    ----------
    zeme : str nebo None
        Hodnota ze sloupce Země (např. 'CZ', 'US', 'SK').

    Vrací
    -----
    str
        Kód jazyka pro spaCy ('cs' nebo 'en').
    """
    if not zeme:
        return "cs"  # výchozí čeština
    zeme = zeme.strip().upper()
    if zeme in ("CZ", "CZE"):
        return "cs"
    return "en"  # ostatní jazyky → angličtina (fallback)


# --- Phase 4 OPTIMIZACE ---
# NER a Sentiment_SM jsou vymezena jako commented out – focus na dezinformace

def _analizovat_ner_sm(text, zeme=""):
    """
    Provede NER pomocí spaCy pro daný text. (Phase 4: commentováno pro optimalizaci API)

    Parameters
    ----------
    text : str
        Text k analýze (sloupec Plné znění).
    zeme : str nebo None
        Hodnota ze sloupce Země pro detekci jazyka.

    Vrací
    -----
    list[dict]
        Seznam entit ve formátu [{'word': '<entita>', 'group': '<typ>'}].
        Pokud je text prázdný, vrátí prázdný seznam.
    """
    if not text:
        return []

    # Model inicializován pouze jednou díky _init_ner_analyzer() singletonu
    analyzer = _get_model("ner")  # type: ignore
    lang = _detect_jazyk_zeme(zeme)

    try:
        entities = analyzer.ner(text, lang=lang)
        return [{"word": e["slovo"], "group": e["skupina"]} for e in entities]
    except Exception as exc:
        print(f"⚠️ Chyba NER (small model) pro text: {exc}")
        return []


def _analizovat_sentiment_sm(text):
    """
    Provede sentiment analýzu pomocí BERT multi-lang (nlptown/bert-base-multilingual-uncased-sentiment).

    Parameters
    ----------
    text : str
        Text k analýze (sloupec Plné znění).

    Vrací
    -----
    dict
        Sentiment výsledek ve formátu:
        {'label': '<predikovaná hodnota>', 'score': <float>,
         'sentiment': '<negativní|pozitivní|neutrální>'}
        Pokud je text prázdný, vrátí prázdný slovník.

    Poznámka ke skóre:
        Skóre představuje jistotu modelu v predikci dané sentimentové kategorie (1-5 star rating).
        Nemá přímou interpretaci jako intenzita sentimentu — je to pravděpodobnost, že text
        spadá do predikované kategorie. Např. score=0.71 znamená vysokou jistotu, že text je
        negativní, ne nutně silný negativní sentiment.
    """
    if not text:
        return {}

    try:
        analyzer = _get_model("sentiment")  # type: ignore
        result = analyzer.sentiment(text)
        return {
            "label": result.get("label", ""),
            "score": float(result.get("score", 0.0)),
            "sentiment": result.get("sentiment", "").lower(),
        }
    except Exception as exc:
        print(f"⚠️ Chyba sentiment (BERT multi) pro text: {exc}")
        return {}


def _analizovat_dezinformace_batch(radky):
    """
    Provede batch detekci dezinformací pro VŠECH řádků najednou.

    Parameters
    ----------
    radky : list[dict[str, str]]
        Seznam přetvořených řádků CSV (musí mít stejný počet jako původní řádky).

    Vrací
    -----
    list[dict]
        Výsledek v pořadí odpovídajícím vstupním radkám:
        [{'label': '...', 'score': 0.0}, ...]
        Prázdný slovník pro řádky s prázdným textem.
    """
    # Accumulace všech textů najednou (batch processing)
    texts = []
    for r in radky:
        plne_znani = r.get("Plné znění", "")
        anotace = r.get("Anotace", "").strip() if not plne_znani else ""
        text_pro_analyzi = plne_znani or anotace
        texts.append(text_pro_analyzi)

    # Inicializace modelu pouze JEDNOU (singleton pattern - Phase 4 OPTIMIZACE)
    detekce = _get_model("dezinformace")  # type: ignore
    labels = ["fake news", "reliable news"]

    try:
        # GPU/MPS optimalizace: batch_size=len(texts) umožňuje paralelní
        # zpracování všech textů najednou na MPS (Apple Silicon) nebo CUDA
        results = detekce(
            texts, candidate_labels=labels, batch_size=len(texts) if len(texts) > 1 else 1
        )
        out = []
        for res in results:
            out.append({
                "label": res["labels"][0],
                "score": float(res["scores"][0]),
            })
        return out
    except Exception as exc:
        print(f"⚠️ Chyba dezinformace detekce (batch) pro {len(texts)} textů: {exc}")
        # Vrací prázdný výsledek s délkou odpovídající počtu vstupních řádků
        return [{"label": "", "score": 0.0} for _ in texts]


def _init_ner_analyzer():
    """Inicializace NER analyzátoru (spaCy) — volat pouze jednou."""
    if _MODEL_CACHE["ner"] is None:
        print("⚙️ Inicializuji spaCy NER model (jednou)...")
        _MODEL_CACHE["ner"] = ner_spacy()


def _init_sentiment_analyzer():
    """Inicializace sentiment analyzátoru (BERT multi-lang).

    Model má vlastní lazy-load v src/sentiment_BERT_multi.py, takže tato funkce slouží
    pouze pro konzistenci inicializačního procesu.
    """
    if _MODEL_CACHE["sentiment"] is None:
        print("⚙️ Inicializuji BERT multi-lang sentiment model...")
        _MODEL_CACHE["sentiment"] = sentiment_BERT_multi()


def _init_dezinformace_analyzer():
    """Inicializace dezinformačního detektoru (bart-large-mnli) — volat pouze jednou."""
    if _MODEL_CACHE["dezinformace"] is None:
        print("⚙️ Inicializuji BART zero-shot classifier (jednou, pro všechny řádky)...")
        _MODEL_CACHE["dezinformace"] = hf_pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )


# =============================================================================
# Phase 5 – LLM analýza (sentiment_LLM, NER_LLM)
# =============================================================================

def _analizovat_llm(text, zeme=""):
    """
    Provede NER a sentiment analýzu pomocí lokálního LLM v jednom HTTP volání.

    Prompt je odvozen od src/llm.py (stejné system message, stejná struktura JSON odpovědi).
    URL endpoint: http://{host}:{port}/v1/chat/completions  — OpenAI kompatibilní přístupový bod

    Parameters
    ----------
    text : str
        Text k analýze (sloupec Plné znění).
    zeme : str nebo None
        Hodnota ze sloupce Země pro detekci jazyka.

    Vrací
    -----
    dict
        {'ner': {...}, 'sentiment': '', 'text': '<odstřižený text>'}
        Pokud je text prázdný, vrátí prázdný dict. Pokud endpoint není dostupný,
        vrátí chybovou zprávu s hodnotami na null/empty.
    """
    from src.newton_one.llm_analyzer import _analizovat_llm as _llm

    return _llm(text, zeme)


def _analizovat_ner_llm(text, zeme=""):
    """Provede NER pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)


def _analizovat_sentiment_llm(text, zeme=""):
    """Provede sentiment analýzu pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)


# =============================================================================
# Hlavní funkce
# =============================================================================

def main():
    """Hlavní vstupní bod skriptu."""
    description = (
        "CLI utilita pro načtení NewtonOne CSV souboru a konverzi do JSONL formátu"
        " pro následnou analýzu."
    )
    parser = argparse.ArgumentParser(
        prog='newton_one.py',
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-c", "--csv", help="cesta k semicolon-delimited CSV souboru")
    parser.add_argument("-o", "--output", help="výstupní JSONL soubor")

    args = parser.parse_args()

    if not args.csv or not args.output:
        parser.print_help()
        exit(0)

    # Kontrola existenci vstupního souboru
    if not os.path.exists(args.csv):
        print(f"❌ Vstupní CSV soubor {args.csv} neexistuje.")
        exit(1)

    # Načtení dat
    radky = nacti_csv(args.csv)
    if not radky:
        print("⚠️ Žádné řádky k zpracování.")
        exit(0)

    # =============================================================================
    # Phase 4 OPTIMIZACE: Inicializace modelů JEDNOU — ZAKOMENTOVÁNO pro testování LLM
    # Není potřeba šahat na HuggingFace, pokud nepoužíváme její modely.
    # =============================================================================
    # _init_ner_analyzer()
    # _init_sentiment_analyzer()
    # _init_dezinformace_analyzer()

    print(f"\n⚙️ Phase 4 OPTIMIZACE: Zakomentováno pro testování LLM Phase 5.")
    print()

    # =============================================================================
    # Phase 3 – Analýza každého řádku (malé modely) — ZAKOMENTOVÁNO pro testování LLM
    # =============================================================================
    vysledky = []
    total = len(radky)  # pro signalizaci průběhu LLM výzvy
    for i, r in enumerate(radky):
        vysledek = pretvorit_radku(r)

        # Text pro analýzu: priorita Plné znění > Anotace
        plne_znani = vysledek.get("Plné znění", "")
        anotace = vysledek.get("Anotace", "").strip() if not plne_znani else ""
        text_pro_analyzi = plne_znani or anotace
        zeme = vysledek.get("Země", "")

        # NER_SM (small model) — ZAKOMENTOVÁNO pro testování LLM Phase 5
        # if text_pro_analyzi:
        #     vysledek["NER_SM"] = _analizovat_ner_sm(text_pro_analyzi, zeme)

        # Sentiment_SM (small model BERT multi-lang) — ZAKOMENTOVÁNO pro testování LLM Phase 5
        # if text_pro_analyzi:
        #     vysledek["Sentiment_SM"] = _analizovat_sentiment_sm(text_pro_analyzi)

        # Dezinformace – OPTIMIZACE Phase 4 (GPU/MPS batch + singleton) — ZAKOMENTOVÁNO pro testování LLM Phase 5
        # dez_res = _analizovat_dezinformace_batch(radky)
        # vysledek["Dezinformace"] = dez_res[i] if i < len(dez_res) else {}

        # =============================================================================
        # Phase 5 – LLM analýza (sentiment_LLM, NER_LLM) – JEDNO volání na endpoint
        # =============================================================================
        percent = (i + 1) / total * 100
        filled = int(percent / 2)
        bar = "█" * filled + "░" * (50 - filled)
        print(f"\r{bar} {i+1}/{total} ({percent:.0f}%)\n", end="")

        if text_pro_analyzi:
            llm_result = _analizovat_ner_llm(text_pro_analyzi, zeme)
            vysledek["NER_LLM"] = llm_result.get("ner", {})
            vysledek["sentiment_LLM"] = llm_result.get("sentiment", "")
            vysledek["dezinformace_LLM"] = llm_result.get("dezinformace", "")
            vysledek["klíčová slova_LLM"] = llm_result.get("klíčová slova", "")

        vysledky.append(vysledek)

    # Zápis do JSONL
    ulozit_jsonl(vysledky, args.output)


if __name__ == "__main__":
    main()
