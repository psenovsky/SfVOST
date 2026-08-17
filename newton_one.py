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
import configparser                                           # práce s config.ini
import json                                                   # serializace JSON
import os                                                     # operace se systémem
import urllib.request                                          # HTTP volání do lokálního LLM endpointu
from datetime import datetime                                 # práce s daty

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

# Singleton cache pro inicializaci modelů jednou (Phase 4 – optimalizace API volání)
_MODEL_CACHE = {
    "ner": None,                # spaCy NER instance
    "sentiment": None,          # nlptown/bert-base-multilingual-uncased-sentiment text-classification
    "dezinformace": None,       # bart-large-mnli zero-shot classifier (WORST OFFENDER - optimized here)
}


def _get_model(model_key: str):
    """Vrátí singleton instanci modelu — inicializuje se pouze jednou."""
    if _MODEL_CACHE[model_key] is not None:
        return _MODEL_CACHE[model_key]

# Konfigurace LLM endpointu (Phase 5 – analýza pomocí lokálního LLM)
_llm_config = configparser.RawConfigParser()
_llm_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")


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
        if velkost_input != 0:
            print(f"⚠️ Výstupní soubor {cesta_output} již existuje ({velkost_input} B). Přepisuji ho.")

    # Uložit
    count = 0
    with open(cesta_output, "w", encoding=JSONL_ENCODING) as f:
        for radka in radky:
            json_str = json.dumps(radka, ensure_ascii=False, sort_keys=True)
            f.write(json_str + "\n")
            count += 1

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


def _analizovat_sentiment_sm(text: str) -> dict:
    """
    Provede sentiment analýzu pomocí BERT multi-lang (nlptown/bert-base-multilingual-uncased-sentiment).

    Parametry
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


def _analizovat_dezinformace_batch(radky: list[dict[str, str]]) -> list[dict]:
    """
    Provede batch detekci dezinformací pro VŠECH řádků najednou.

    Parametry
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

def _analizovat_llm(text: str, zeme: str | None = "") -> dict:
    """
    Provede NER a sentiment analýzu pomocí lokálního LLM v jednom HTTP volání.

    Prompt je odvozen od src/llm.py (stejné system message, stejná struktura JSON odpovědi).
    URL endpoint: http://{host}:{port}/v1/chat/completions  — OpenAI kompatibilní přístupový bod

    Parametry
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
    if not text:
        return {"ner": {}, "sentiment": "", "text": ""}

    cfg = _check_llm_config()
    if not cfg["valid"]:
        print(f"⚠️ NER_LLM/Sentiment_LLM: {cfg['message']}")
        return {"ner": {}, "sentiment": "", "text": text[:2000]}

    # Odstranit text nad maximální délku (LLM má limit)
    trunc_limit = 20000
    odstřiženy_text = text[:trunc_limit]

    messages = [
        {
            "role": "system",
            "content": ("""
                Jsi expert na analýzu textu a lingvistiku. Tvým úkolem je provést detailní analýzu
                příspěvků ze sociálních sítí a zpravodajství.

                Pro každý příspěvek aktivně vyhledej a extrahuj všechny pojmenované entity (NER),
                urči sentiment a vyhodnoť přítomnost dezinformací.

                Vrať výsledek VŽDY jako validní JSON pole (array), kde každý prvek odpovídá jednomu příspěvku v pořadí zadaném na vstupu.

                Struktura každého prvku v poli:
                {{
                  "ner": {{
                    "PER": ["Petr Pavel"],"
                    "ORG": ["Škoda Auto", "PČR"],"
                    "LOC": ["Vysoké Tatry"],"
                    "GPE": ["Česká republika", "Praha"],"
                    "DATE": ["včera", "17. srpna"],"
                    "FAC": ["Letiště Václava Havla"]
                  }},
                  "sentiment": "pozitivní | neutrální | negativní",
                  "dezinformace": "ano | ne",
                  "klíčová slova": ["tornádo", "riziko"]
                }}

                Pravidla pro zpracování:

                1. NER: Prohledej text a extrahuj všechna vlastní jména a specifické údaje do odpovídajících kategorií:
                  - Nejprve identifikuj všechny pojmenované entity v textu.
                  - Každou nalezenou entitu zařaď do odpovídající kategorie.
                  - Entity uváděj přesně tak, jak se vyskytují v textu.
                  - Duplicitní výskyty odstraň.
                  - Pokud pro danou kategorii žádná entita neexistuje, vrať [].

                 Kategorie NER:
                   - PER: Jména lidí a osobností
                   - ORG: Společnosti, firmy, instituce, úřady, spolky
                   - LOC: Geografické objekty, pohoří, řeky, přírodní památky
                   - GPE: Geopolitické entity (státy, města, kraje, obce)
                   - DATE: Data, dny, časové údaje a období
                   - FAC: Budovy, letiště, stavby, infrastruktura

                 Pokud text obsahuje osoby, organizace, lokality nebo data, musí být uvedeny v odpovídajících seznamech.

                 Nevracej prázdné seznamy, pokud jsou v textu zjevně přítomné relevantní entity..

                2. Sentiment: Vyber právě jednu hodnotu: "pozitivní", "neutrální" nebo "negativní".
                3. Dezinformace: Vyhodnoť pravdivost na základě znepokojivého tónu, konspirací či obecných faktů. Vyber "ano" nebo "ne".
                4. Klíčová slova: Identifikuj všechna klíčová slova charakterizující hodnocený příspěvek. Klíčových slov by nemělo být více než 10.
                5. Výstup: Vrať výhradně čistý JSON bez jakýchkoliv komentářů nebo omáčky kolem."
                """
            )
        },
        {"role": "user", "content": odstřiženy_text}
    ]

    # URL podle OpenAI kompatibilního schématu: http://{host}:{port}/v1/chat/completions
    url = f"http://{cfg['host']}:{cfg['port']}/v1/chat/completions"

    #print(messages[0]["content"]) # DEBUG smazat
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode())
            obsah = result["choices"][0]["message"]["content"].strip()

            if obsah.startswith("```"):
                řádky = obsah.split("\n")
                obsah = "\n".join(řádky[1:-1])

            výsledek = json.loads(obsah)
        post = výsledek[0] if isinstance(výsledek, list) and len(výsledek) > 0 else {}
    except Exception as exc:
        print(f"⚠️ Chyba NER_LLM/Sentiment_LLM pro text: endpoint neodpověděl nebo selhal ({exc})")
        return {"ner": {}, "sentiment": "", "text": odstřiženy_text}

    entities = {
        "PER": post.get("ner", {}).get("PER", []),
        "ORG": post.get("ner", {}).get("ORG", []),
        "LOC": post.get("ner", {}).get("LOC", []),
        "GPE": post.get("ner", {}).get("GPE", []),
        "DATE": post.get("ner", {}).get("DATE", []),
        "FAC": post.get("ner", {}).get("FAC", []),
    }

    return {
        "text": odstřiženy_text,
        "ner": entities,
        "sentiment": post.get("sentiment", "").lower(),
        "dezinformace": post.get("dezinformace", "").lower(),
        "klíčová slova": post.get("klíčová slova", []),
    }


def _analizovat_ner_llm(text: str, zeme: str | None = "") -> dict:
    """Provede NER pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)


def _analizovat_sentiment_llm(text: str, zeme: str | None = "") -> dict:
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
