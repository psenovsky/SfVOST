# -*- coding: utf-8 -*-

"""Analýza příspěvků pomocí lokálního LLM endpointu (Phase 5)."""

import json as _json
import urllib.request


from src.newton_one.config_loader import _check_llm_config, MAX_LLM_RETRY
from src.newton_one.models import UNICODE_WHITESPACE

# Kategorie NER, které se vyhledávají v odpovědi LLM
NER_KATEGORIE = ("PER", "ORG", "LOC", "GPE", "DATE", "FAC")


def _clean_text(text):
    """Odstraní Unicode whitespace z textu."""
    return "".join(ch for ch in text if ch not in UNICODE_WHITESPACE).strip()


def _prazdne_entity():
    """Vrátí prázdnou strukturu NER (používá se jako stub při chybě nebo neúplné odpovědi)."""
    return {klic: [] for klic in NER_KATEGORIE}


def _seznam(hodnota):
    """Vynutí hodnotu na seznam (LLM místo pole vrací i objekt, None nebo jediný řetězec)."""
    if isinstance(hodnota, list):
        return [polozka for polozka in hodnota if polozka is not None]
    if isinstance(hodnota, str):
        return [hodnota] if hodnota.strip() else []
    return []


def _text(hodnota, nazev):
    """Vynutí hodnotu na řetězec s malými písmeny; cokoliv jiného než text → prázdný řetězec."""
    if isinstance(hodnota, str):
        return hodnota.lower()
    if hodnota:
        print(f"⚠️ {nazev}: LLM vrátilo neočekávaný typ ({type(hodnota).__name__}), použita prázdná hodnota")
    return ""


def _ma_uzitecnou_odpoved(post):
    """Zjistí, zda odpověď LLM obsahuje alespoň sentiment, tedy zda je použitelná k uložení."""
    sentiment = post.get("sentiment")
    return bool(post) and isinstance(sentiment, str) and bool(sentiment.strip())


def _normalizuj_vysledek(post):
    """Převede odpověď LLM na typy, kterých očekává výstup i následná analýza v R.

    Odpověď lokálního LLM je volný textový výstup, takže jednotlivé klíče mohou
    chybět nebo mít neočekávaný typ (např. ``"ner": []`` místo objektu nebo
    ``"sentiment": null``). Každá hodnota se proto zkontroluje a převede na
    očekávaný typ; chybějící hodnota se nahradí prázdnou, ne aby skončila výjimkou.

    Vrací
    -----
    tuple
        (entities, sentiment, dezinformace, klicova_slova) jako (dict, str, str, list).
    """
    ner = post.get("ner")
    if isinstance(ner, dict):
        entities = {klic: _seznam(ner.get(klic)) for klic in NER_KATEGORIE}
    else:
        # None (klíč chybí / null) je běžné a není chyba, jiný typ už ano
        if ner is not None:
            print(f"⚠️ NER_LLM: LLM vrátilo neočekávaný typ klíče 'ner' ({type(ner).__name__}), použity prázdné entity")
        entities = _prazdne_entity()

    return (
        entities,
        _text(post.get("sentiment"), "Sentiment_LLM"),
        _text(post.get("dezinformace"), "dezinformace_LLM"),
        _seznam(post.get("klíčová slova")),
    )


def _ověřit_endpoint():
    """Jednorázová kontrola dostupnosti LLM endpointu před zpracováním dat.

    Provádí lehké volání OpenAI-kompatibilního health-check bodu /v1/models.

    Vrací
    -----
    tuple(bool, str)
        (True, None) pokud je konfigurace platná a endpoint odpovídá na volání.
        (False, msg) jinak spolu s popisem chyby.
    """
    cfg = _check_llm_config()
    if not cfg["valid"]:
        return False, cfg["message"]

    try:
        req = urllib.request.Request(
            f"http://{cfg['host']}:{cfg['port']}/v1/models", method="GET",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            response.read()
    except Exception as exc:
        return False, f"endpoint neodpověděl nebo selhal ({exc})"

    return True, None


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
        Klíč 'ok' vyjadřuje, zda proběhla skutečná úspěšná LLM analýza (True),
        nebo zda byl vrácen jen stub při chybě / prázdném textu (False). Volající
        jej používá k počítání řádků bez úspěšné LLM analýzy; odpověď bez sentimentu
        se považuje za neúspěšnou, aby se řádek zpracoval znovu (viz Plan 2 v AGENTS.md).
        Odpověď je vždy normalizována na očekávané typy (dict / str / list), takže
        chybějící či neočekávaně typovaný klíč nesmí shodit běh – vrací se stub.
        Pokud je text prázdný, vrátí prázdný dict. Pokud endpoint není dostupný,
        vrátí chybovou zprávu s hodnotami na null/empty.
    """
    if not text:
        return {"ner": {}, "sentiment": "", "text": "", "ok": False}

    cfg = _check_llm_config()
    if not cfg["valid"]:
        print(f"⚠️ NER_LLM/Sentiment_LLM: {cfg['message']}")
        return {"ner": {}, "sentiment": "", "text": text[:2000], "ok": False}

    # Odstranit text nad maximální délku (LLM má limit)
    trunc_limit = 20000
    odstřiženy_text = _clean_text(text)[:trunc_limit]

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
                  - pamatuj, že analyzuje zprávy, které jsou relevantní pro krizové štáby, mohou se týkat povodní, tornád, velkých požárů apod., tedy jednoznačně negativních jevů.
                  - zpráva, která takové jevy pouze popisuje tak, jak se staly, není sama o sobě negativní - je neutrální
                  - pozitivní nebo negativní sentiment je možno odvodit, pouze pokud v textu se vyskytuje nějaký soud
                  - příkladem pozitivního sentimentu by mohlo být vzedmutí vlny solidarity, pozitivní hodnocení činnosti zasahujících složek, apod.
                  - příkladem negativního sentimentu by mohlo být pozdní reakce na událost, chybná metodika zásahu, apod.

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

    # Inicializace výchozí hodnoty, aby po vyčerpání pokusů nedošlo k NameError
    post = {}
    uspech = False

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }

    for pokus in range(MAX_LLM_RETRY):
        try:
            req = urllib.request.Request(
                url, data=_json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=300) as response:
                result = _json.loads(response.read().decode())
                obsah = result["choices"][0]["message"]["content"].strip()

                if obsah.startswith("```"):
                    řádky = obsah.split("\n")
                    obsah = "\n".join(řádky[1:-1])

                výsledek = _json.loads(obsah)
            prvni = výsledek[0] if isinstance(výsledek, list) and len(výsledek) > 0 else None
            # Odpověď musí být objekt; cokoliv jiného (None, string, číslo) = neúplná analýza
            post = prvni if isinstance(prvni, dict) else {}
            uspech = _ma_uzitecnou_odpoved(post)
        except Exception as exc:
            print(f"⚠️ Chyba NER_LLM/Sentiment_LLM pro text: endpoint neodpověděl nebo selhal ({exc})")
            if pokus == MAX_LLM_RETRY - 1:
                break
            continue

        # Úspěšná odpověď = rovnou ukončit smyčku (opakovat se má jen neúspěch).
        if uspech:
            break

    # Normalizace běží ve vlastním try/except: rozbitá odpověď LLM nesmí shodit celý běh,
    # ale má degradovat na stub (prázdné hodnoty + ok=False) jako ostatní chyby.
    try:
        entities, sentiment, dezinformace, klicova_slova = _normalizuj_vysledek(post)
    except Exception as exc:
        print(f"⚠️ Chyba NER_LLM/Sentiment_LLM: neočekávaný formát odpovědi LLM ({exc})")
        entities, sentiment, dezinformace, klicova_slova = _prazdne_entity(), "", "", []
        uspech = False

    return {
        "text": odstřiženy_text,
        "ner": entities,
        "sentiment": sentiment,
        "dezinformace": dezinformace,
        "klíčová slova": klicova_slova,
        "ok": uspech and bool(sentiment),
    }


def _analizovat_ner_llm(text, zeme=""):
    """Provede NER pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)


def _analizovat_sentiment_llm(text, zeme=""):
    """Provede sentiment analýzu pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)
