"""
Název: SfVOST_LLM.py
Popis: Tento skript provádí analýzu příspěvků ze sítě BlueSky uložených ve formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py

Soubor vygeneruje:
- NER
- překlad příspěvku do českého jazyka
- sentiment příspěvku
- dezinformace příspěvku

K vyhodnocení se používá lokální LLM provozovaný pomocí LM-Studio nebo Ollama.

použití:
--------
    uv SfVOST_LLM.py -p <souborJSONL> -o <souborJSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -p, --postJSON souborJSONL - soubor JSON s příspěvky
- -s, --sentiment souborJSONL - soubor JSON s výstupy analýzy

Autor: Pavel Šenovský
Datum: 2026-02-16
"""

import argparse  # argumenty příkazového řádku
import json  # JSON parsing
import os
import re  # regular expressions
import urllib.request  # make HTTP requests
from multiprocessing import Condition

import pandas as pd
from numpy import ulong
from torch.fx.experimental.proxy_tensor import prim
from torch.utils.checkpoint import NoDefault
from tqdm import tqdm  # progress bar

from src.utils import (
    check_config_ini,  # kontrola konzistence config.ini
    uloz_json,  # uložení JSON do souboru
)

# iniciace globálních proměnných
out = None  # výstup modelu
conf = None  # konfigurační soubor
postPath = ""  # cesta k souboru s příspěvky
postsOutPath = ""  # cesta k souboru s výstupem
postsJSONL = None  # načtené příspěvky
language_map = None  # slovník s jazyky


def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global sen, conf, postPath, postsOutPath
    # zpracování argumentů příkazové řádky
    description = "Program analysuje příspěvky ze sociálních sítí poskytnuté v JSONL souboru a odvodí NER, sentiment, překlad a dezinformace."
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

    # try:
    if not os.path.exists(args.postJSON):
        print(f"❌ Soubor s příspěvky {args.postJSON} neexistuje")
        exit()

    conf = check_config_ini()
    # project_root = os.path.dirname(os.path.abspath(__file__))
    # postsPath = os.path.join(project_root, "..", args.postJSON)
    # postsOutPath = os.path.join(project_root, "..", args.out)
    postsPath = args.postJSON
    postsOutPath = args.out
    print(f"✅ ... dokončení inicializace")  # DEBUG
    LLM(postsPath, postsOutPath)
    # except Exception as e:
    #    print(f"❌ Chyba při inicializaci: {e}")
    #    print(f"Detaily výjimky: {str(e)}")
    #    exit()


def LLM(postsPath, postsOutPath):
    """
    provede načtení příspěvků ze souboru a jejich zpracování pomocí LLM

    Parametry:
    ----------
    postsPath - cesta k souboru s příspěvky
    postsOutPath - cesta k souboru s výsledky

    Vrací:
    ------
    None
    """
    global postsJSONL, conf
    obsah = []
    with open(postsPath, "r", encoding="utf-8") as file:
        postsJSONL = file.readlines()

    msg = ""
    # for line in postsJSONL:
    prispevky = 0
    for line in tqdm(postsJSONL, desc="Zpracování příspěvků", unit="line"):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            msg += f"❌ Chyba při načítání příspěvku: {line}"
            continue

        lang = data["record"]["langs"][0]  # první jazyk v příspevku
        lang_nazev = get_language_name(lang)
        post = data["record"]["text"]
        prompt = f"""Jsi expert na analýzu textu a lingvistiku. Tvým úkolem je analyzovat a přeložit příspěvek ze sociální sítě BlueSky.
        Příspěvek je v jazyce: {lang_nazev}.

        Vrať výsledek VŽDY jako validní JSON s následující strukturou:
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
        4. JSON: Neuváděj žádné úvodní řeči ani vysvětlení, pouze čistý JSON.

        Příspěvek k analýze:
        {post}"""

        payload = {
            "model": conf["LLM"]["model"],
            # "prompt": prompt,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": conf["LLM"]["max_tokens"],
            "temperature": conf["LLM"]["temperature"],
            # "stream": False,
        }
        # LM‑Studio endpoint
        ip = conf["LLM"]["host"]
        port = conf["LLM"]["port"]
        url = f"http://{ip}:{port}/v1/chat/completions"
        data_llm = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data_llm, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                vysledek = json.loads(
                    result["choices"][0]["message"]["content"].strip()
                )
        except urllib.error.HTTPError as e:
            print("Status:", e.code)
            print("Body:", e.read().decode())  # <- tohle ukaže konkrétní důvod 400
            raise

        data["post_CZ"] = vysledek["preklad"]
        data["ner"] = vysledek["ner"]
        data["sentiment"] = vysledek["sentiment"]
        data["dezinformace"] = vysledek["dezinformace"]
        obsah.append(data)

    print(f"✅ ... zpracován {len(obsah)} příspěvků")
    uloz_prispevky(obsah)
    exit()


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


def uloz_prispevky(out):
    """
    Uloží příspěvky do souboru.

    Parametry:
    ----------
    out - seznam příspěvků

    Vrací:
    ------
    vsechny_prispevky : list of models.AppBskyFeedPost
        seznam příspěvků vytěžených ze sítě BlueSky
    """
    global postsOutPath
    # uloz_json(self.nerJSONL, self.ner)
    with open(postsOutPath, "w", encoding="utf-8") as f:
        for post in out:
            f.write(json.dumps(post))
            f.write("\n")
    print(f"✅ ... uloženo do souboru {postsOutPath}")


# Hlavní funkce
def main():
    global postsOutPath, out, language_map
    df = pd.read_csv("data/ISO639.csv", sep=";")
    language_map = (
        df.dropna(subset=["ISO 639-1"]).set_index("ISO 639-1")["název"].to_dict()
    )  # vytvoření slovníku s jazyky
    print(f"✅ ... vytvořen slovník jazyků")  # DEBUG
    check_config()  # kontrola konzistence config.ini
    uloz_json(postsOutPath, out)


if __name__ == "__main__":
    main()
