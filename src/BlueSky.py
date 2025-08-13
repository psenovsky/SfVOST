"""
Název: BlueSky.py
Popis: Načítá příspěvky ze sociální sítě BlueSky
Autor: Pavel Šenovský
Datum: 2025-08-11

Třída pro těžení příspěvků podle klíčových slov ze sociální sítě BlueSky.
"""
import configparser                                     # práce s konfiguračními soubory typu init
import os
import time
import csv                                              # zpracování CSV souborů
from atproto import Client, models                      # API BlueSky
from datetime import datetime, timedelta, timezone      # čas, datum, zóny
from src.utils import check_config_ini, is_valid_date, uloz_json

class BlueSky:

    postJSONL = ""
    keywords = ""
    lang = ""
    since = ""
    until = ""

    def __init__(self, postJSONL, keywords, lang = "cs", since = None, until = None):
        """
        Iniciace třídy

        Parametry:
        ----------
        postJSONL - soubor JSON s příspěvky
        keywordsJSONL - soubor JSON s klíčovými slovy, případně hashtagy
        lang - jazyk oddělené čárkou, které se má vyhledávat (en, cs, sk), cs je výchozí
        since - datum, od kterého se mají vytěžovat příspěvky v ISO formátu (YYYY-MM-DD)
        until - datum, do kterého se mají vytěžovat příspěvky (včetně) v ISO formátu (YYYY-MM-DD), implicitně je použito aktuální datum

        Raises:
        -------
        Exception - v případě, že konfigurační soubor není správně nakonfigurován
        """
        self.config = configparser.RawConfigParser()
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.postJSONL = os.path.join(project_root, '..', postJSONL)
        self.keywords = os.path.join(project_root, '..', keywords)
        self.lang = lang
        self.since = since
        self.until = until
        r = self.check_config()
        if not r["validace"]:
            raise Exception(r["zprava"])
        self.keywords = self.nacti_klicova_slova()
        self.keywords_joined = " OR ".join(self.keywords)
        r = self.tezba_prispevky()
        if not r["result"]:
            raise Exception(r["zprava"])
        self.prispevky = r["vsechny_prispevky"]

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
        if not self.postJSONL:
            error += "❌ musí být zadán soubor, kam se mají ukládat příspěvky\n"

        if not self.keywords:
            error += "❌ musí být zadán soubor, ze které se budou načítat klíčová slova\n"
        elif not os.path.exists(self.keywords):
            error += "❌ soubor se seznamem klíčových slove neexistuje."

        # T0D0:... je vyžadováno kvůli chybě v API BlueSky. V dokumentaci API je uvedeno, že stačí datum v ISO formátu, ale v praxi se jedná o časové razítko.
        # chyba je nahlášena, ale není opravena (přestože je to už rok) ... takže se jedná o workaround
        if not self.since:
            cas_limitu = datetime.now(timezone.utc) - timedelta(days=int(self.config["casove_limity"]["historie_dni"]))
            self.config.set("BlueSky", "since", cas_limitu.strftime("%Y-%m-%dT00:00:00.000Z"))
        else:
            if not is_valid_date(self.since):
                error += "❌ datum od (since) není ve formátu YYYY-MM-DD"
            else:
                d = datetime.strptime(self.since, '%Y-%m-%d')
                self.config.set("BlueSky", "since", d.strftime("%Y-%m-%dT00:00:00.000Z"))
        if not self.until:
            self.config.set("BlueSky", "until", datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:00.000Z"))
        else:
            if not is_valid_date(self.until):
                error += "❌ datum do (until) není ve formátu YYYY-MM-DD"
            else:
                d = datetime.strptime(self.until, '%Y-%m-%d')
                self.config.set("BlueSky", "until", d.strftime("%Y-%m-%dT23:59:00.000Z"))
        if error != "":
            return {
                "validace": False,
                "zprava": error
            }

        if not self.lang:
            self.config.set("BlueSky", "lang", "cs")
            self.langs = ["cs"]
        else:
            self.config.set("BlueSky", "lang", self.lang)
            self.langs = self.lang.split(",")

        self.config.add_section("cesty")
        self.config.set("cesty", "json_vystup", self.postJSONL)
        self.config.set("cesty", "keywords", self.keywords)
        return {
            "validace": True,
            "zprava": ""
        }

    def nacti_klicova_slova(self):
        """
        Načte klíčová slova z souboru self.keywords.

        Vrací:
        ------
        keywords : list of str
            seznam klíčových slov
        """
        keywords = []
        with open(self.config['cesty']['keywords'], newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader) # Skip header
            for row in reader:
                if row:
                    keywords.append(row[0])
        return keywords

    def tezba_prispevky(self):
        """
        Vyhledá příspěvky ze sociální sítě BlueSky.

        Vrací:
        ------
        vsechny_prispevky : list of models.AppBskyFeedPost
            seznam příspěvků vytěžených ze sítě BlueSky
        """
        klient = Client()
        profil = klient.login(self.config['BlueSky']['user'], self.config['BlueSky']['password'])
        vsechny_prispevky = []
        cursor = None

        print(f"Těžím příspěvky od: {self.config['BlueSky']['since']}")
        error = ""
        try:
            for l in self.langs:
                while True:
                    params = models.AppBskyFeedSearchPosts.Params(
                        q = self.keywords_joined,
                        since = self.config['BlueSky']['since'],
                        until = self.config['BlueSky']['until'],
                        lang = l,
                        limit = 100,
                        cursor = cursor
                    )
                    vysledky = klient.app.bsky.feed.search_posts(params)
                    vsechny_prispevky.extend(vysledky.posts)

                    if not vysledky.cursor:
                        break # žádné další stránky

                    cursor = vysledky.cursor
                    time.sleep(int(self.config["casove_limity"]["zpozdeni_mezi_dotazy"]))

                print(f"✅ Příspěvky v {l} vytěženy")
                time.sleep(int(self.config["casove_limity"]["zpozdeni_mezi_dotazy"]))
        except Exception as e:
            error = f"❌ Chyba při vytěžování příspěvků: {e}\nDetaily výjimky: {str(e)}"
            return {
                "result": False,
                "zprava": error
            }

        return {
            "result": True,
            "vsechny_prispevky": vsechny_prispevky
        }

    def uloz_prispevky(self):
        """
        Uloží příspěvky do souboru.

        Vrací:
        ------
        vsechny_prispevky : list of models.AppBskyFeedPost
            seznam příspěvků vytěžených ze sítě BlueSky
        """
        uloz_json(self.config['cesty']['json_vystup'], self.prispevky)
