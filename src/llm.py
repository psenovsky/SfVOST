"""
Název: llm.py
Popis: analýza příspěvků pomocí lokálního LLM (překlad, NER, sentiment, dezinformace)
Autor: Pavel Šenovský
Datum: 2026-07-27
"""
import configparser
import json
import os
import urllib.request

import pandas as pd

from src.utils import check_config_ini
from src.models import Post, nacti_prispevky_z_jsonl

MAX_RETRY = 3


class llm:
    def __init__(self, postsPath, postsJSONL=""):
        """
        Iniciace třídy

        Parametry:
        ----------
        postsPath - cesta k JSONL souboru s příspěvky
        postsJSONL - list[Post] příspěvky v paměti
        """
        self.config = configparser.RawConfigParser()
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.postsPath = os.path.join(project_root, '..', postsPath)
        self.postsJSONL = postsJSONL
        self.language_map = None

        r = self.check_config()
        if not r["validace"]:
            raise Exception(r["zprava"])

        if os.path.exists(self.postsPath):
            self.mode = "soubor"
        elif self.postsJSONL != "":
            self.mode = "text"
        else:
            raise Exception("❌ soubor JSON s příspěvky nebo list příspěvků nebyl zadán")

        self._nacti_jazyky()

        r = self.analyzuj_llm()
        if not r["result"]:
            raise Exception(r["zprava"])

        self.llm = r["vsechny_prispevky"]

    def check_config(self):
        """
        Provede kontrolu integrity konfiguračního souboru.
        """
        result = check_config_ini()
        if isinstance(result, configparser.RawConfigParser):
            self.config = result
        else:
            return {
                "validace": False,
                "zprava": result
            }

        error = ""
        if not self.postsPath and self.postsJSONL == "":
            error += "❌ pro analýzu LLM je potřeba zadat cestu k souboru nebo příspěvky v paměti\n"
        elif self.postsJSONL == "" and not os.path.exists(self.postsPath):
            error += "❌ soubor JSON s příspěvky neexistuje\n"
        if error != "":
            return {
                "validace": False,
                "zprava": error
            }
        return {
            "validace": True,
            "zprava": ""
        }

    def _nacti_jazyky(self):
        """
        Načte mapování kódů jazyků na názvy z data/ISO639.csv
        """
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ISO639.csv')
        df = pd.read_csv(csv_path, sep=";")
        self.language_map = (
            df.dropna(subset=["ISO 639-1"])
            .set_index("ISO 639-1")["název"]
            .to_dict()
        )

    def _get_language_name(self, code):
        """
        Vrátí název jazyka z kódu ISO 639-1
        """
        return self.language_map.get(code, f"Neznámý jazyk ({code})")

    def analyzuj_llm(self):
        """
        Provede analýzu příspěvků pomocí LLM v dávkách.

        Vrací:
        ------
        dict s výsledkem operace
        """
        if self.mode == "soubor":
            prispevky = nacti_prispevky_z_jsonl(self.postsPath)
        else:
            prispevky = self.postsJSONL

        batch_size = int(self.config["LLM"]["batch_size"])
        ip = self.config["LLM"]["host"]
        port = self.config["LLM"]["port"]
        url = f"http://{ip}:{port}/v1/chat/completions"

        dávky = [prispevky[i:i + batch_size] for i in range(0, len(prispevky), batch_size)]
        zpracováno = 0

        for dávka in dávky:
            prompt = self._sestroj_dávkový_prompt(dávka)
            max_tokens_dávka = int(self.config["LLM"]["max_tokens"]) * len(dávka)

            payload = {
                "model": self.config["LLM"]["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens_dávka,
                "temperature": self.config["LLM"]["temperature"],
            }

            výsledky = self._odešli_dávku(url, payload, len(dávka))

            if výsledky is None:
                continue

            for i, post in enumerate(dávka):
                if i < len(výsledky):
                    v = výsledky[i]
                    post.preklad = v.get("preklad", "")
                    post.ner = v.get("ner", {})
                    post.sentiment = v.get("sentiment", "")
                    post.dezinformace = v.get("dezinformace", "")
                zpracováno += 1

        if zpracováno == 0:
            return {
                "result": False,
                "zprava": "❌ LLM analýza selhala - žádné příspěvky nebyly zpracovány"
            }

        return {
            "result": True,
            "vsechny_prispevky": prispevky
        }

    def _sestroj_dávkový_prompt(self, dávka):
        """
        Sestaví prompt pro dávkové zpracování příspěvků.
        """
        sekce = []
        for i, post in enumerate(dávka):
            lang = post.record.langs[0]
            lang_nazev = self._get_language_name(lang)
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

    def _odešli_dávku(self, url, payload, počet_příspěvků):
        """
        Odešle dávku na LLM endpoint a vrátí pole výsledků.
        Při selhání opakuje až MAX_RETRYkrát.
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

                    if obsah.startswith("```"):
                        řádky = obsah.split("\n")
                        obsah = "\n".join(řádky[1:-1])

                    výsledky = json.loads(obsah)

                    if not isinstance(výsledky, list):
                        continue

                    if len(výsledky) != počet_příspěvků:
                        continue

                    return výsledky

            except (urllib.error.HTTPError, json.JSONDecodeError, Exception):
                continue

        return None
