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
from src.ner_spacy import ner_spacy

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
        Provede identifikaci pojmenovaných entit pomocí spaCy frameworku.

        Parametry:
        ----------
        None

        Vrací:
        ------
        dict
            Slovník s výsledky analýzy NER

        doplní k příspěvkům ze sociální sítě BlueSky identifikované NER.
        """
        obsah = []
        prispevky = 0
        preskoceno = 0
        spacy_ner = ner_spacy()

        ner_models = self._nacti_ner_modely()

        if self.mode == "soubor":
            self.postsJSONL = nacti_prispevky_z_jsonl(self.postsPath)

        msg = ""
        for post in self.postsJSONL:
            prispevky += 1
            try:
                lang = post.record.langs[0]  # first language in post
                if lang in ner_models:
                    model_name = ner_models[lang]
                    post.ner = spacy_ner.ner(post.record.text, lang, model_name)
                else:
                    preskoceno += 1
                    msg += f"⚠️ Příspěvek v jazyce {lang} není nakonfigurován pro NER, přeskakuji příspěvek {post.uri}\n"
                obsah.append(post)
            except Exception as e:
                msg += f"❌ Chyba při zpracování příspěvku: {e}\n"

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

    def _nacti_ner_modely(self) -> dict:
        """
        Načte konfiguraci NER modelů z config.ini.

        Vrací:
        ------
        dict
            Slovník mapující kód jazyka na název spaCy modelu
        """
        default_models = {
            "en": "en_core_web_lg",
            "cs": "cs_core_news_lg",
            "bg": "bg_core_news_lg",
            "pl": "pl_core_news_lg",
            "ru": "ru_core_news_lg",
            "uk": "uk_core_news_lg"
        }

        try:
            if self.config.has_section('ner') and self.config.has_option('ner', 'modely'):
                modely_json = self.config.get('ner', 'modely')
                return json.loads(modely_json)
        except (json.JSONDecodeError, configparser.NoSectionError, configparser.NoOptionError):
            pass

        return default_models
