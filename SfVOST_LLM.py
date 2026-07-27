"""
Název: SfVOST_LLM.py
Popis: Tento skript provádí analýzu příspěvků ze sítě BlueSky uložených ve formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py

Soubor vygeneruje:
- NER
- překlad příspěvku do českého jazyka
- sentiment příspěvku
- dezinformace příspěvku

K vyhodnocení se používá lokální LLM provozovaný pomocí LM-Studio nebo Ollama.
Příspěvky se zpracovávají dávkově (batch processing) pro efektivnější využití LLM.

použití:
--------
    uv SfVOST_LLM.py -p <souborJSONL> -o <souborJSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -p, --postJSON souborJSONL - soubor JSON s příspěvky
- -o, --out souborJSONL - soubor JSON s výstupy analýzy

Autor: Pavel Šenovský
Datum: 2026-02-16
"""

import argparse  # argumenty příkazového řádku
import json  # JSON parsing
import os
import urllib.request  # make HTTP requests

import pandas as pd
from tqdm import tqdm  # progress bar

from src.utils import (
    check_config_ini,  # kontrola konzistence config.ini
    uloz_json,  # uložení JSON do souboru
)
from src.models import Post, nacti_prispevky_z_jsonl, uloz_prispevky_do_jsonl

# iniciace globálních proměnných
out = None  # výstup modelu
conf = None  # konfigurační soubor
postsPath = ""  # cesta k souboru s příspěvky
postsOutPath = ""  # cesta k souboru s výstupem
language_map = None  # slovník s jazyky

MAX_RETRY = 3  # maximální počet opakování při selhání dávky


def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global conf, postsPath, postsOutPath
    # zpracování argumentů příkazové řádky
    description = "Program analyzuje příspěvky ze sociálních sítí poskytnuté v JSONL souboru a odvodí NER, sentiment, překlad a dezinformace."
    parser = argparse.ArgumentParser(
        prog="SfVOST_LLM.py",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-p", "--postJSON", help="soubor JSONL s příspěvky")
    parser.add_argument("-o", "--out", help="soubor JSONL s výsledky")
    args = parser.parse_args()
    if not args.postJSON or not args.out:
        parser.print_help()
        exit()

    if not os.path.exists(args.postJSON):
        print(f"❌ Soubor s příspěvky {args.postJSON} neexistuje")
        exit()

    conf = check_config_ini()
    postsPath = args.postJSON
    postsOutPath = args.out
    print(f"✅ ... dokončení inicializace")
    LLM(postsPath, postsOutPath)


def LLM(postsPath, postsOutPath):
    """
    Provede načtení příspěvků ze souboru a jejich zpracování pomocí LLM v dávkách.

    Příspěvky se rozdělí na dávky podle konfigurace batch_size.
    Každá dávka se odešle jako jeden požadavek na LLM, který vrátí JSON pole
    s výsledky pro všechny příspěvky v dávce.

    Parametry:
    ----------
    postsPath - cesta k souboru s příspěvky
    postsOutPath - cesta k souboru s výsledky

    Vrací:
    ------
    None
    """
    global conf

    prispevky = nacti_prispevky_z_jsonl(postsPath)
    batch_size = int(conf["LLM"]["batch_size"])
    ip = conf["LLM"]["host"]
    port = conf["LLM"]["port"]
    url = f"http://{ip}:{port}/v1/chat/completions"

    # rozdělení příspěvků na dávky
    dávky = [prispevky[i:i + batch_size] for i in range(0, len(prispevky), batch_size)]
    zpracováno = 0

    for dávka_idx, dávka in enumerate(tqdm(dávky, desc="Zpracování dávek", unit="dávka")):
        prompt = _sestroj_dávkový_prompt(dávka)
        max_tokens_dávka = int(conf["LLM"]["max_tokens"]) * len(dávka)

        payload = {
            "model": conf["LLM"]["model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens_dávka,
            "temperature": conf["LLM"]["temperature"],
        }

        výsledky = _odešli_dávku(url, payload, len(dávka))

        if výsledky is None:
            print(f"❌ Dávka {dávka_idx + 1} selhala i po {MAX_RETRY} pokusech, přeskakuji")
            continue

        for i, post in enumerate(dávka):
            if i < len(výsledky):
                v = výsledky[i]
                post.preklad = v.get("preklad", "")
                post.ner = v.get("ner", {})
                post.sentiment = v.get("sentiment", "")
                post.dezinformace = v.get("dezinformace", "")
            zpracováno += 1

    print(f"✅ ... zpracováno {zpracováno} z {len(prispevky)} příspěvků")
    uloz_prispevky_do_jsonl(prispevky, postsOutPath)
    exit()


def _sestroj_dávkový_prompt(dávka):
    """
    Sestaví prompt pro dávkové zpracování příspěvků.

    Parametry:
    ----------
    dávka : list[Post]
        seznam příspěvků v jedné dávce

    Vrací:
    ------
    str - prompt pro LLM
    """
    sekce = []
    for i, post in enumerate(dávka):
        lang = post.record.langs[0]
        lang_nazev = get_language_name(lang)
        sekce.append(f"[{i}] (jazyk: {lang_nazev})\n{post.record.text}")

    příspěvky_text = "\n\n".join(sekce)

    return f"""Jsi expert na analýzu textu a lingvistiku. Tvým úkolem je analyzovat a přeložit příspěvky ze sociální sítě BlueSky.

Vrať výsledek VŽDY jako validní JSON pole (array), kde každý prvek odpovídá jednomu příspěvku v pořadí, v jakém byly zadány.
Každý prvek pole má tuto strukturu:
{{
  "preklad": "Text přeložený do češtiny. Pokud je originál v češtině, vrať jej beze změny.",
  "ner": {{
    "PER": ["seznam osob"],
    "ORG": ["seznam organizací"],
    "LOC": ["seznam lokalit"],
    "GPE": ["seznam geopolitických entit"],
    "DATE": ["seznam dat"],
    "FAC": ["seznam zařízení/staveb"]
  }},
  "sentiment": "pozitivní | neutrální | negativní",
  "dezinformace": "ano | ne"
}}

Pravidla pro zpracování:
1. NER: Pokud v textu žádná entita daného typu není, vrať prázdný seznam [].
2. Sentiment: Vyber pouze jednu z nabízených možností.
3. Dezinformace: Vyhodnoť na základě obecně známých faktů a tónu příspěvku (např. očividné konspirační teorie).
4. JSON: Neuváděj žádné úvodní řeči ani vysvětlení, pouze čisté JSON pole.
5. Počet prvků v odpovědi MUSÍ být přesně {len(dávka)}.

Příspěvky k analýze:
{příspěvky_text}"""


def _odešli_dávku(url, payload, počet_příspěvků):
    """
    Odešle dávku na LLM endpoint a vrátí pole výsledků.
    Při selhání opakuje až MAX_RETRYkrát.

    Parametry:
    ----------
    url : str
        URL endpointu LLM
    payload : dict
        tělo požadavku
    počet_příspěvků : int
        očekávaný počet výsledků v poli

    Vrací:
    ------
    list or None - pole výsledků nebo None při selhání
    """
    data_llm = json.dumps(payload).encode("utf-8")

    for pokus in range(MAX_RETRY):
        try:
            req = urllib.request.Request(
                url, data=data_llm, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode())
                obsah = result["choices"][0]["message"]["content"].strip()

                # odstranění případných markdown obalů kolem JSON
                if obsah.startswith("```"):
                    řádky = obsah.split("\n")
                    obsah = "\n".join(řádky[1:-1])

                výsledky = json.loads(obsah)

                if not isinstance(výsledky, list):
                    print(f"⚠️ Očekáváno pole, obdrženo {type(výsledky).__name__}")
                    continue

                if len(výsledky) != počet_příspěvků:
                    print(f"⚠️ Očekáváno {počet_příspěvků} výsledků, obdrženo {len(výsledky)}")
                    continue

                return výsledky

        except urllib.error.HTTPError as e:
            print(f"⚠️ HTTP chyba (pokus {pokus + 1}/{MAX_RETRY}): {e.code}")
            if pokus < MAX_RETRY - 1:
                print(f"   {e.read().decode()}")
        except json.JSONDecodeError as e:
            print(f"⚠️ Nevalidní JSON odpověď (pokus {pokus + 1}/{MAX_RETRY}): {e}")
        except Exception as e:
            print(f"⚠️ Neočekávaná chyba (pokus {pokus + 1}/{MAX_RETRY}): {e}")

    return None


def get_language_name(code):
    """
    Funkce pro bezpečné vrácení názvu jazyka z kódu ISO 639-1

    Parametry:
    ----------
    code - kód jazyka

    Vrací:
    ------
    str - název jazyka
    """
    return language_map.get(code, f"Neznámý jazyk ({code})")


# Hlavní funkce
def main():
    global language_map
    df = pd.read_csv("data/ISO639.csv", sep=";")
    language_map = (
        df.dropna(subset=["ISO 639-1"]).set_index("ISO 639-1")["název"].to_dict()
    )
    print(f"✅ ... vytvořen slovník jazyků")
    check_config()


if __name__ == "__main__":
    main()
