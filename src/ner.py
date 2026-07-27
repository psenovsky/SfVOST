"""
Název: ner.py
Popis: analýza pojmenovaných entit (NER)
Autor: Pavel Šenovský
Datum: 2025-08-11
"""
import configparser                                     # práce s konfiguračními soubory typu init
import os
import json                                             # zpracování JSON souborů

from src.utils import check_config_ini
from src.models import Post, nacti_prispevky_z_jsonl, uloz_prispevky_do_jsonl
from src.ner_CZ import ner_CZ
from src.ner_BERT_EN import ner_BERT_EN

class ner:
    def __init__(self, postsPath, nerJSONL, postsJSONL = ""):
        """
        Iniciace třídy

        Parametry:
        ----------
        postsPath - soubor JSON s příspěvky
        nerJSONL - cesta, kam se má uložit soubor JSON s pojmenovanými entitami
        postsJSONL - obsah JSONL (text)

        Raises:
        -------
        Exception - v případě, že konfigurační soubor není správně nakonfigurován
        """
        self.config = configparser.RawConfigParser()
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.postsPath = os.path.join(project_root, '..', postsPath)
        self.nerJSONL = os.path.join(project_root, '..', nerJSONL)
        self.postsJSONL = postsJSONL
        r = self.check_config()
        if not r["validace"]:
            raise Exception(r["zprava"])
        if os.path.exists(self.postsPath):
            self.mode = "soubor"
        elif self.postsJSONL != "":
            self.mode = "text"
        else:
            raise Exception("❌ soubor JSON s příspěvky nebo JSONL text s příspěvky neexistuje")

        r = self.analyzuj_ner()
        if not r["result"]:
            raise Exception(r["zprava"])

        self.ner = r["vsechny_prispevky"]

    def check_config(self):
        """
        Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů a připraví konfigurační slovník pro další použití v aplikaci.
        """
        result = check_config_ini() # kontrola config.ini
        # chyba parsování config.ini
        if isinstance(result, configparser.RawConfigParser):
            self.config = result
        else:
            return {
                "validace": False,
                "zprava": result
            }

        error = ""
        if not self.postsPath  and self.postsJSONL == "":
            error += "❌ pro identifikaci je potřeba JSON s příspěvky zpřístupnit buďto cestou k souboru, nebo zadání JSON předáním textu\n"
        elif self.postsJSONL == "" and not os.path.exists(self.postsPath):
            error += "❌ soubor JSON s příspěvky neexistuje\n"
        if not self.nerJSONL:
            error += "❌ pro uložení pojmenovaných entit musí být zadán cesta k souboru\n"
        if error != "":
            return {
                "validace": False,
                "zprava": error
            }
        return {
            "validace": True,
            "zprava": ""
        }

    def analyzuj_ner(self):
        """
        Provede identifikaci pojmenovaných entit

        Parametry:
        ----------
        None

        Vrací:
        ------
        None

        doplní k příspěvkům ze sociální sítě BlueSky identifikované NER.
        """
        obsah = []
        prispevky = 0
        preskoceno = 0
        bert_en = ner_BERT_EN()
        ner_cz = ner_CZ()
        if self.mode == "soubor":
            self.postsJSONL = nacti_prispevky_z_jsonl(self.postsPath)

        msg = ""
        for post in self.postsJSONL:
            prispevky += 1
            try:
                lang = post.record.langs[0]  # first language in post
                if lang == 'en':
                    post.ner = bert_en.ner(post.record.text)
                elif lang in ['cs', 'bg', 'pl', 'ru', 'uk']:
                    post.ner = ner_cz.ner(post.record.text)
                else:
                    preskoceno += 1
                    msg += f"❌ příspěvek v neznámém jazyce {lang}, přeskakuji příspěvek {post.uri}"
                obsah.append(post)
            except Exception as e:
                msg += f"❌ Chyba při zpracování příspěvku: {e}"

        if not obsah:
            error = "⚠️ Varování: Žádné platné příspěvky nebyly načteny. Zkontrolujte soubor, který načítáte."
            return {
                "result": False,
                "zprava": error
            }
        else:
            return {
                "result": True,
                "vsechny_prispevky": obsah,
                "msg": msg
            }

    def uloz_prispevky(self):
        """
        Uloží příspěvky do souboru.

        Vrací:
        ------
        vsechny_prispevky : list of models.AppBskyFeedPost
            seznam příspěvků vytěžených ze sítě BlueSky
        """
        uloz_prispevky_do_jsonl(self.ner, self.nerJSONL)
