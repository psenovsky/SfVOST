# -*- coding: utf-8 -*-

"""
Název: newton_one.py
Popis: CLI utilita pro načtení NewtonOne CSV souboru (nebo JSONL výstupu scraperu) a konverzi do JSONL formátu pro následnou analýzu.

použití:
--------
    python newton_one.py -c <cesta_k_CSV> -o <cesta_k_JSONL>
    python newton_one.py -c <cesta_k_JSONL> -o <cesta_k_JSONL>
    python newton_one.py --opravit -o <cesta_k_JSONL>

Parametry:
----------
- -h, --help     - zobrazí nápovědu a skončí
- -c, --csv      - cesta k semicolon-delimited CSV souboru nebo JSONL (povinné)
- -o, --output   - výstupní JSONL soubor (povinné)
- --opravit      - vyčistí výstupní JSONL (odstraní záznamy bez úspěšné LLM analýzy
                   a duplicity) a skončí; vstupní CSV se v tomto režimu nenačítá

Autor: Pavel Šenovský
Datum: 2026-08-14
"""

import argparse                                              # argumenty příkazového řádku
import os                                                     # operace se systémem

from tqdm import tqdm                                         # progress bar

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

from src.newton_one.data_io import (
    chybi_llm_analyza,                                 # záznam vyžaduje znovu LLM analýzu
    kod_radku,                                         # identifikátor záznamu
    nacti_csv,
    nacti_jsonl,
    opravit_vystup,                                    # vyčištění výstupu od neúspěšných LLM analýz
    precteni_stav_vystupu,                             # stav výstupu pro navázání (resume)
    pretvorit_radku,
    text_pro_analyzu,                                  # text k analýze (Plné znění > Anotace)
    ulozit_radku_jsonl,  # průběžné ukládání jednotlivých záznamů
)


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
    OUTPUT_DELIMITER,
    SLoupce,
    UNICODE_WHITESPACE,
)

from src.newton_one.llm_analyzer import _analizovat_llm as _llm
from src.newton_one.llm_analyzer import _ověřit_endpoint


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
        {'ner': {...}, 'sentiment': '', 'text': '<odstřižený text>', 'ok': bool}
        Klíč 'ok' (False při chybě, True při úspěšné analýze) slouží k počítání
        řádků bez úspěšné LLM analýzy.
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

def _vycistit_vystup(cesta_output):
    """
    Vyčistí výstupní JSONL a informuje o výsledku.

    Odstraní záznamy, na kterých selhala LLM analýza (ty se znovu zpracují
    při příštím běhu) a duplicitní záznamy. Původní soubor zůstane jako záloha
    s příponou '.bak'.

    Parameters
    ----------
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.

    Vrací
    -----
    dict
        Výsledek opravy (počty odstraněných záznamů a zapsaných řádků).
    """
    if not os.path.exists(cesta_output):
        print(f"⚠️ Výstupní soubor {cesta_output} neexistuje – není co opravovat.")
        return {"bez_llm": 0, "duplikaty": 0, "poskozeno": 0, "zapsano": 0}

    vysledek = opravit_vystup(cesta_output)
    if not (vysledek["bez_llm"] or vysledek["duplikaty"] or vysledek["poskozeno"]):
        print(f"✅ Výstupní soubor {cesta_output} je čistý, není co opravovat ({vysledek['zapsano']} záznamů).")
        return vysledek

    print(f"🛠️  Opraven výstupní soubor {cesta_output} (záloha: {cesta_output}.bak):")
    print(f"   odstraněno {vysledek['bez_llm']} záznamů bez úspěšné LLM analýzy")
    print(f"   odstraněno {vysledek['duplikaty']} duplicitních záznamů")
    if vysledek["poskozeno"]:
        print(f"   odstraněno {vysledek['poskozeno']} nečitelných záznamů")
    print(f"   zůstává {vysledek['zapsano']} záznamů – odstraněné záznamy se znovu zpracují při příštím běhu")
    return vysledek


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
    parser.add_argument("-c", "--csv", help="cesta k semicolon-delimited CSV souboru nebo JSONL (výstup scraperu)")
    parser.add_argument("-o", "--output", help="výstupní JSONL soubor")
    parser.add_argument(
        "--opravit",
        action="store_true",
        help="vyčistí výstupní JSONL (odstraní záznamy bez úspěšné LLM analýzy a duplicity) a skončí",
    )

    args = parser.parse_args()

    # =============================================================================
    # Jednorázová oprava výstupního JSONL – bez čtení vstupních dat.
    # =============================================================================
    if args.opravit:
        if not args.output:
            print("❌ Pro opravu výstupu je nutné zadat cestu k výstupnímu JSONL souboru (-o).")
            exit(1)
        _vycistit_vystup(args.output)
        return

    if not args.csv or not args.output:
        parser.print_help()
        exit(0)

    # Kontrola existenci vstupního souboru
    if not os.path.exists(args.csv):
        print(f"❌ Vstupní soubor {args.csv} neexistuje.")
        exit(1)

    # Detekce formátu vstupu (CSV nebo JSONL). JSONL je výstup scraperu – již
    # přetvořená data, proto se nepoužívá pretvorit_radku.
    je_jsonl = args.csv.lower().endswith(".jsonl")

    if je_jsonl:
        radky = nacti_jsonl(args.csv)
    else:
        radky = nacti_csv(args.csv)

    if not radky:
        print("⚠️ Žádné řádky k zpracování.")
        exit(0)

    # =============================================================================
    # Průběžné ukládání + navázání (resume): zjistit již zpracované záznamy.
    # Stav je jediným zdrojem pravdy – výstupní JSONL soubor. Přečteme si z něj
    # identifikátory sloupce 'Kód článku' a při dalším spuštění přeskočíme řádky,
    # které už byly úspěšně zpracovány (např. po výpadku proudu / přerušení).
    #
    # Za zpracovaný se považuje jen záznam, na kterém skutečně proběhla LLM analýza.
    # Záznamy, na kterých LLM selhala, se znovu zpracují – jinak by chybějící data
    # zůstala chybět navždy. Nejprve je proto z výstupu vyřadíme, aby po opětovném
    # zpracování nevznikly duplicity (záznam se průběžně doplňuje na konec souboru).
    # =============================================================================
    stav_vystupu = precteni_stav_vystupu(args.output)
    zpracovane_kody = stav_vystupu["hotove_kody"]
    chybi_llm_kody = stav_vystupu["chybi_llm_kody"]
    print(f"🔄 Navazuji na {len(zpracovane_kody)} již zpracovaných záznamů ({args.output})")
    if chybi_llm_kody or stav_vystupu["duplikaty"] or stav_vystupu["poskozeno"]:
        _vycistit_vystup(args.output)

    # =============================================================================
    # Phase 5 – Ověření dostupnosti LLM endpointu JEDNORÁZ před zpracováním
    # Pokud endpoint není dostupný, ukončíme s jednou jasnou zprávou místo
    # per-řádkového špinění chyb a případného crashu (NameError po vyčerpání pokusů).
    # =============================================================================
    neuspesne_llm = 0
    uspesne_llm = 0
    llm_ok, llm_msg = _ověřit_endpoint()
    if not llm_ok:
        print(f"❌ LLM analýza není k dispozici: {llm_msg}")
        exit(1)

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
    i_skocne = 0
    znovu_zpracovano = 0
    zpracovano = 0
    for i, r in enumerate(tqdm(radky, desc="Zpracování řádků", unit="řádek", total=len(radky))):
        if je_jsonl:
            vysledek = r  # JSONL záznamy jsou již přetvořené (výstup scraperu)
        else:
            vysledek = pretvorit_radku(r)

        # Navázání: přeskočit řádky, které už byly úspěšně zpracovány a uloženy.
        kod = kod_radku(vysledek)
        if kod and kod in zpracovane_kody:
            i_skocne += 1
            continue

        # Text pro analýzu: priorita Plné znění > Anotace
        text_pro_analyzi = text_pro_analyzu(vysledek)
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
        if text_pro_analyzi:
            llm_result = _analizovat_ner_llm(text_pro_analyzi, zeme)
            vysledek["NER_LLM"] = llm_result.get("ner", {})
            vysledek["sentiment_LLM"] = llm_result.get("sentiment", "")
            vysledek["dezinformace_LLM"] = llm_result.get("dezinformace", "")
            vysledek["klíčová slova_LLM"] = llm_result.get("klíčová slova", "")
            if llm_result.get("ok"):
                uspesne_llm += 1
            else:
                neuspesne_llm += 1

        # Průběžné ukládání – každý záznam se dopíše okamžitě po analýze,
        # nikoliv až na konci. Při přerušení ztratíme jen právě tento řádek.
        ulozit_radku_jsonl(vysledek, args.output)
        zpracovano += 1

        # Zápisem hotový kód přidáme mezi zpracované, aby se duplicitní kód ve vstupu
        # znovu neanalyzoval ani nezapsal podruhé. Záznam, na kterém LLM selhala (nebo
        # který nemá text), se mezi hotové nepočítá – musí se zpracovat znovu (Plan 2).
        if kod and not chybi_llm_analyza(vysledek):
            zpracovane_kody.add(kod)
        if kod and kod in chybi_llm_kody:
            znovu_zpracovano += 1

    # Výstupní shrnutí výsledku do konzole
    analyzovano = uspesne_llm + neuspesne_llm
    print(f"\n✅ Hotovo: {zpracovano} řádků zpracováno průběžně → {args.output}")
    print(f"   🔄 Přeskočeno {i_skocne} již zpracovaných záznamů")
    if znovu_zpracovano:
        print(f"   ♻️  Znovu zpracováno {znovu_zpracovano} záznamů, na kterých předtím selhala LLM analýza")
    if neuspesne_llm:
        print(f"   ⚠️  LLM analýza (NER_LLM / Sentiment_LLM / klíčová slova_LLM): částečně neúspěšná "
              f"({uspesne_llm} z {analyzovano} analyzovaných řádků)")
        print(f"   ⚠️  {neuspesne_llm} řádků bez úspěšné LLM analýzy")
    else:
        print(f"   ✅ LLM analýza (NER_LLM / Sentiment_LLM / klíčová slova_LLM): OK "
              f"({analyzovano} analyzovaných řádků)")


if __name__ == "__main__":
    main()
