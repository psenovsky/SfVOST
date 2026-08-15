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
import csv                                                    # čtení CSV souborů
import json                                                   # serializace JSON
import os                                                     # operace se systémem
from datetime import datetime                                 # práce s daty

# Import analyzátorů malých modelů (Phase 3)
from config_loader import ConfigLoader                        # čtení config.ini

# NER a Sentiment imports – Phase 4: commented out, kept for reference only
try:
    from src.ner_spacy import ner_spacy                       # NER via spaCy (commented out - Phase 4 focus: dezinformace)
except ImportError:
    ner_spacy = None                                          # type: ignore

try:
    from src.sentiment_Czert_B import sentiment_Czert_B       # Sentiment via Czert-B (commented out - Phase 4 focus: dezinformace)
except ImportError:
    sentiment_Czert_B = None                                  # type: ignore

from transformers.pipelines import pipeline as hf_pipeline     # Disinformation detection — OPTIMIZED in Phase 4

# Singleton cache pro inicializaci modelů jednou (Phase 4 – optimalizace API volání)
_MODEL_CACHE = {
    "ner": None,                # spaCy NER instance
    "sentiment": None,          # Czert-B pipeline instance  
    "dezinformace": None,       # bart-large-mnli zero-shot classifier (WORST OFFENDER - optimized here)
}


def _get_model(model_key: str):
    """Vrátí singleton instanci modelu — inicializuje se pouze jednou."""
    if _MODEL_CACHE[model_key] is not None:
        return _MODEL_CACHE[model_key]


# Konfigurace Phase 4 – optimalizace API volání
_cfg = ConfigLoader()
_BATCH_SIZE = int(_cfg.get_int("newton_one", "batch_size", fallback=50))



# Unicode znaky, které by mohly být mezernatami v číslech (např. U+00A0 nbsp, U+2007 thin space)
UNICODE_WHITESPACE = "\xa0\u2007\u2008\u2009\u200a\u205f\u3000"


# =============================================================================
# Konstanty
# =============================================================================

CSV_SEP = ";"                                                 # odliovník sloupců v NewtonOne CSV
ENCODING = "utf-8"                                            # kódování vstupního souboru
JSONL_ENCODING = "utf-8"                                      # kódování výstupního souboru
OUTPUT_DELIMITER = "\t"                                       # oddělovač klíčů v JSON (pro determinismus)


# Sloupci, které budeme extrahovat z CSV
SLoupce = [
    {"nazev": "Kód článku",     "typ": str},
    {"nazev": "Datum publikování", "typ": str},
    {"nazev": "Název",          "typ": str},
    {"nazev": "Zdroj",           "typ": str},
    {"nazev": "Země",            "typ": str},
    {"nazev": "Typ média",       "typ": str},
    {"nazev": "Anotace",         "typ": str},
    {"nazev": "Plné znění",      "typ": str},
    {"nazev": "Typ zprávy",      "typ": str},
    {"nazev": "Sentiment",       "typ": str},
    {"nazev": "Dosah",           "typ": int, "strip_space": True},
]


# =============================================================================
# Funkce
# =============================================================================

def parse_datum(date_str: str) -> str | None:
    """
    Zkusí přeměnit řetězec na formát YYYY-MM-DD.

    Parameters
    ----------
    date_str : str
        Datum v libovolném formátu (např. '25.06.2021 00:00').

    Vrací
    -----
    str nebo None
        Formátované datum YYYY-MM-DD, pokud je parsovatelné; jinak původní řetězec.
    """
    if not date_str or not isinstance(date_str, str):
        return date_str

    date_str = date_str.strip()
    for formát in ("%Y-%m-%d", "%d.%m.%Y %H:%M"):
        try:
            datetime.strptime(date_str, formát)
            return datetime.strptime(date_str, formát).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Pokud žádný formát nevyfunčí, vrátíme původní hodnotu
    return date_str


def nacti_csv(cesta_csv: str) -> list[dict[str, str]]:
    """
    Načte semicolon-delimited CSV soubor a vrací seznam slovníků.

    Parameters
    ----------
    cesta_csv : str
        Cesta k vstupnímu CSV souboru.

    Vrací
    -----
    list[dict[str, str]]
        Seznam řádků jako slovníky s klíči odpovídajícími názvům sloupců v CSV.
    """
    if not os.path.exists(cesta_csv):
        print(f"❌ Vstupní CSV soubor neexistuje: {cesta_csv}")
        return []

    radky = []
    with open(cesta_csv, "r", encoding=ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_SEP)
        for jazyk in reader:
            if not jazyk or all(not v.strip() for v in jazyk.values()):
                continue
            radky.append(jazyk)

    print(f"✅ Načteno {len(radky)} řádků z souboru {cesta_csv}")
    return radky


def pretvorit_radku(radka: dict[str, str]) -> dict[str, str]:
    """
    Přetvoří jeden řádek CSV na JSON objekt podle definice SLoupce.

    Parameters
    ----------
    radka : dict[str, str]
        Jeden řádek z CSV (klíče jsou názvy sloupců).

    Vrací
    -----
    dict[str, str]
        Přetvořený řádek s vypsáním hodnot a formátováním dat.
    """
    vysledek = {}
    for sloupec in SLoupce:
        nazev = sloupec["nazev"]
        hodnota = radka.get(nazev, "")

        # Strhání mezernat ze všech hodnot (včetně Unicode whitespace)
        if sloupec.get("strip_space"):
            hodnota = "".join(ch for ch in hodnota if ch not in UNICODE_WHITESPACE).strip()

        if not hodnota:
            hodnota = ""

        # Datum publikování formátujeme na YYYY-MM-DD
        if nazev == "Datum publikování":
            hodnota = parse_datum(hodnota) or hodnota

        # Dosah → integer
        if nazev == "Dosah" and sloupec.get("typ") == int:
            try:
                hodnota = int(float(hodnota))  # float→int pro případ desetinných čísel
            except (ValueError, TypeError):
                hodnota = ""

        vysledek[nazev] = hodnota

    return vysledek


def ulozit_jsonl(radky: list[dict[str, str]], cesta_output: str) -> int:
    """
    Uloží řádky do JSONL souboru se sorted keys pro determinismus.

    Parameters
    ----------
    radky : list[dict[str, str]]
        Seznam přetvořených řádků.
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.

    Vrací
    -----
    int
        Počet zapsaných řádků.
    """
    if not radky:
        print("⚠️ Žádné data pro zápis.")
        return 0

    # Zkontrolovat, zda soubor již existuje
    if os.path.exists(cesta_output):
        velkost_input = os.path.getsize(cesta_output)
        if velkost_input == 0:
            print(f"⚠️ Výstupní soubor {cesta_output} je prázdný, přepsu ho.")
        else:
            print(f"⚠️ Výstupní soubor {cesta_output} již existuje ({velkost_input} B). Přepisuji ho.")

    # Uložit
    count = 0
    total = len(radky)
    with open(cesta_output, "w", encoding=JSONL_ENCODING) as f:
        for radka in radky:
            json_str = json.dumps(radka, ensure_ascii=False, sort_keys=True)
            f.write(json_str + "\n")
            count += 1

            # Progress bar (50 znaků)
            if count % 10 == 0 or count == total:
                percent = count / total * 100
                filled = int(percent / 2)
                bar = "█" * filled + "░" * (50 - filled)
                print(f"\r{bar} {count}/{total} ({percent:.0f}%)", end="")

    print()
    return count


# =============================================================================
# Funkce pro analýzu malými modely (Phase 3 – NER_SM, Sentiment_SM, Dezinformace)
# =============================================================================

def _detect_jazyk_zeme(zeme: str | None) -> str:
    """
    Určí jazyk na základě sloupce Země.

    Parametry
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

def _analizovat_ner_sm(text: str, zeme: str | None = "") -> list[dict]:
    """
    Provede NER pomocí spaCy pro daný text. (Phase 4: commentováno pro optimalizaci API)

    Parametry
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


def _analizovat_sentiment_sm(text: str, zeme: str | None = "") -> dict:
    """
    Provede sentiment analýzu pomocí Czert-B pro daný text. (Phase 4: commentováno pro optimalizaci API)

    Parametry
    ----------
    text : str
        Text k analýze (sloupec Plné znění).
    zeme : str nebo None
        Hodnota ze sloupce Země pro detekci jazyka.

    Vrací
    -----
    dict
        Sentiment výsledek ve formátu:
        {'label': '<predikovaná hodnota>', 'score': <float>,
         'sentiment': '<negativní|pozitivní|neutrální>'}
        Pokud je text prázdný, vrátí prázdný slovník.
    """
    if not text:
        return {}

    # Model inicializován pouze jednou díky _init_sentiment_analyzer() singletonu
    analyzer = _get_model("sentiment")  # type: ignore

    try:
        result = analyzer.sentiment(text)
        return {
            "label": result.get("label", ""),
            "score": float(result.get("score", 0.0)),
            "sentiment": result.get("sentiment", "").lower(),
        }
    except Exception as exc:
        print(f"⚠️ Chyba sentiment (Czert-B) pro text: {exc}")
        return {}


def _analizovat_dezinformace_batch(radky: list[dict[str, str]]) -> dict[int, dict]:
    """
    Provede batch detekci dezinformací pro VŠECH řádků najednou.

    Parametry
    ----------
    radky : list[dict[str, str]]
        Seznam přetvořených řádků CSV.

    Vrací
    -----
    dict[int, dict]
        Výsledek pro každý řádek indexovaný podle pozice v seznamu:
        {index: {'label': '...', 'score': 0.0}, ...}
    """
    # Accumulace všech textů najednou (batch processing)
    texts = []
    indices = []
    for idx, r in enumerate(radky):
        plne_znani = r.get("Plné znění", "")
        anotace = r.get("Anotace", "").strip() if not plne_znani else ""
        text_pro_analyzi = plne_znani or anotace
        if text_pro_analyzi:
            texts.append(text_pro_analyzi)
            indices.append(idx)

    if not texts:
        return {}

    # Inicializace modelu pouze JEDNOU (singleton pattern - Phase 4 OPTIMIZACE)
    detekce = _get_model("dezinformace")  # type: ignore
    labels = ["fake news", "reliable news"]

    try:
        results = detekce(texts, candidate_labels=labels)
        out = {}
        for idx, res in zip(indices, results):
            out[idx] = {
                "label": res["labels"][0],
                "score": float(res["scores"][0]),
            }
        return out
    except Exception as exc:
        print(f"⚠️ Chyba dezinformace detekce (batch) pro {len(texts)} textů: {exc}")
        return {}


def _init_ner_analyzer():
    """Inicializace NER analyzátoru (spaCy) — volat pouze jednou."""
    if _MODEL_CACHE["ner"] is None:
        print("⚙️ Inicializuji spaCy NER model (jednou)...")
        _MODEL_CACHE["ner"] = ner_spacy()


def _init_sentiment_analyzer():
    """Inicializace sentiment analyzátoru (Czert-B) — volat pouze jednou."""
    if _MODEL_CACHE["sentiment"] is None:
        print("⚙️ Inicializuji Czert-B sentiment model (jednou)...")
        _MODEL_CACHE["sentiment"] = sentiment_Czert_B()


def _init_dezinformace_analyzer():
    """Inicializace dezinformačního detektoru (bart-large-mnli) — volat pouze jednou."""
    if _MODEL_CACHE["dezinformace"] is None:
        print("⚙️ Inicializuji BART zero-shot classifier (jednou, pro všechny řádky)...")
        _MODEL_CACHE["dezinformace"] = hf_pipeline(
            "zero-shot-classification", model="facebook/bart-large-mnli"
        )




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
    # Phase 4 OPTIMIZACE: Inicializace modelů JEDNOU (singleton pattern)
    # =============================================================================
    _init_ner_analyzer()
    _init_sentiment_analyzer()
    _init_dezinformace_analyzer()

    print(f"\n⚙️ Phase 4 OPTIMIZACE: Modely inicializovány jednou (singleton pattern).")
    print(f"   Batch size dezinformace: {_BATCH_SIZE} textů najednou.")
    print()

    # =============================================================================
    # Phase 3 – Analýza každého řádku
    # =============================================================================
    vysledky = []
    for i, r in enumerate(radky):
        vysledek = pretvorit_radku(r)

        # Text pro analýzu: priorita Plné znění > Anotace
        plne_znani = vysledek.get("Plné znění", "")
        anotace = vysledek.get("Anotace", "").strip() if not plne_znani else ""
        text_pro_analyzi = plne_znani or anotace
        zeme = vysledek.get("Země", "")

        # NER_SM (Phase 4: commentováno – focus na dezinformace)
        # if text_pro_analyzi:
        #     vysledek["NER_SM"] = _analizovat_ner_sm(text_pro_analyzi, zeme)

        # Sentiment_SM (Phase 4: commentováno – focus na dezinformace)
        # if text_pro_analyzi:
        #     vysledek["Sentiment_SM"] = _analizovat_sentiment_sm(text_pro_analyzi, zeme)

        # Dezinformace – OPTIMIZACE Phase 4 (batch processing + singleton)
        vysledek["Dezinformace"] = _analizovat_dezinformace_batch(radky)[i] or {}

        vysledky.append(vysledek)

    # Zápis do JSONL
    ulozit_jsonl(vysledky, args.output)


if __name__ == "__main__":
    main()
