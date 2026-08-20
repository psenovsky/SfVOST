# -*- coding: utf-8 -*-

"""Analýza příspěvků pomocí lokálního LLM endpointu (Phase 5)."""

import json as _json
import urllib.request


from src.newton_one.config_loader import _check_llm_config, MAX_LLM_RETRY
from src.newton_one.models import UNICODE_WHITESPACE


def _clean_text(text):
    """Odstraní Unicode whitespace z textu."""
    return "".join(ch for ch in text if ch not in UNICODE_WHITESPACE).strip()


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
    if not text:
        return {"ner": {}, "sentiment": "", "text": ""}

    cfg = _check_llm_config()
    if not cfg["valid"]:
        print(f"⚠️ NER_LLM/Sentiment_LLM: {cfg['message']}")
        return {"ner": {}, "sentiment": "", "text": text[:2000]}

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
            post = výsledek[0] if isinstance(výsledek, list) and len(výsledek) > 0 else {}
        except Exception as exc:
            print(f"⚠️ Chyba NER_LLM/Sentiment_LLM pro text: endpoint neodpověděl nebo selhal ({exc})")
            if pokus == MAX_LLM_RETRY - 1:
                break
            continue

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


def _analizovat_ner_llm(text, zeme=""):
    """Provede NER pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)


def _analizovat_sentiment_llm(text, zeme=""):
    """Provede sentiment analýzu pomocí lokálního LLM. (Phase 5 – nyní volá společnou funkci _analizovat_llm)"""
    return _analizovat_llm(text, zeme)
