"""
Název: sentiment.py
Popis: analýza sentimentu příspěvků
Autor: Pavel Šenovský
Datum: 2025-08-11
"""
import configparser                                     # práce s konfiguračními soubory typu init
import os
import json                                             # zpracování JSON souborů
import regex as re                                      # regulární výrazy s Unicode podporou

from src.utils import check_config_ini
from src.sentiment_BERT_multi import sentiment_BERT_multi
from src.sentiment_Czert_B import sentiment_Czert_B

class sentiment:
    """
    Třída pro analýzu sentimentu příspěvků
    """
    def __init__(self, cestaJSON, cestaExport, postsJSONL = ""):
        """
        Inicializace třídy

        Parametry:
        ----------
            cestaJSON - cesta k JSON souboru s příspěvky
            cestaExport - cesta k douboru, do kterého se budou exportovat výsledky
            postsJSONL - obsah JSONL (text)
        """
        self.config = configparser.RawConfigParser()
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.cestaJSON = os.path.join(project_root, '..', cestaJSON)
        self.cestaExport = os.path.join(project_root, '..', cestaExport)
        self.postsJSONL = postsJSONL
        r = self.check_config()
        if not r["validace"]:
            raise Exception(r["zprava"])
        if cestaJSON != "" and os.path.exists(self.cestaJSON):
            self.mode = "soubor"
        elif self.postsJSONL != "":
            self.mode = "text"
        else:
            raise Exception("❌ soubor JSON s příspěvky nebo JSONL text s příspěvky neexistuje")

        r = self.analyzuj_sentiment()
        if not r["result"]:
            raise Exception(r["zprava"])

        self.sentiment = r["vsechny_prispevky"]

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
        if not self.cestaJSON  and self.postsJSONL == "":
            error += "❌ pro identifikaci je potřeba JSON s příspěvky zpřístupnit buďto cestou k souboru, nebo zadání JSON předáním textu\n"
        elif self.postsJSONL == "" and not os.path.exists(self.cestaJSON):
            error += "❌ soubor JSON s příspěvky neexistuje\n"
        if not self.cestaExport:
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

    def analyzuj_sentiment(self):
        """
        Provede analýzu sentimentu příspěvků

        Parametry:
        ----------
        None

        Vrací:
        ------
        None

        doplní k příspěvkům ze sociální sítě BlueSky informaci o sentimentu
        """
        obsah = []
        prispevky = 0
        preskoceno = 0
        bertMulti = sentiment_BERT_multi()
        czertB = sentiment_Czert_B()
        if self.mode == "soubor":
            with open(self.cestaJSON, 'r', encoding='utf-8') as file:
                self.postsJSONL = file.readlines()

        msg = ""
        for line in self.postsJSONL:
            prispevky += 1
            if self.mode == "soubor":
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    msg += f"❌ Chyba při načítání příspěvku: {line}"
                    continue
            else:  # mode == "text"
                data = line  # už je to slovník

            try:
                t = self.clean_text(data['record']['text'])
                lang = data['record']['langs'][0]
                if lang in ['en', 'nl', 'de', 'fr', 'it', 'es']:
                    data['sentiment'] = bertMulti.sentiment(t)
                elif lang == 'cs':
                    data['sentiment'] = czertB.sentiment(t)
                else:
                    preskoceno += 1
                    msg += f"❌ příspěvek v neznámém jazyce {lang}, přeskakuji řádek {line}"
                obsah.append(data)
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
        with open(self.cestaExport, "w", encoding="utf-8") as f:
            for post in self.sentiment:
                f.write(json.dumps(post))
                f.write("\n")
        print(f"✅ ... uloženo do souboru {self.cestaExport}")

    def clean_text(self, text):
        """
        Provede vyčištění textu, odstraní speciální znaky, emotikony, atd. a převede na malá písmena.

        Params:
        -------
            text (str): text, který chceme vyčistit

        Returns:
        --------
            str: vyčištěný text
        """
        text = re.sub(r'[^\p{L}\s]', '', text)
        return text.lower()
