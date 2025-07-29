"""
Název: SocNetwork.py
Popis: Načítá příspěvky ze zvolené sociální sítě a ukládá je do souboru

Použití:
--------
    python SocNetwork.py [-h] -p <souborJSONL> -k <souborCSV> [-l <lang>] [-od <datum>] [-do <datum>]

Parametry:
----------
    -h, --help  zobrazí nápovědu a skončí
    -p, --postJSON <souborJSONL> soubor JSON s příspěvky
    -k, --keywords <souborCSV> soubor CSV s klíčovými slovy (hashtagy)
    -l, --lang <lang> jazyk oddělené čárkou, které se má vyhledávat (en, cs, sk), cs je výchozí
    -od, --since <datum> datum, od kterého se mají vytěžovat příspěvky v ISO formátu (YYYY-MM-DD)
    -do, --until <datum> datum, do kterého se mají vytěžovat příspěvky (včetně) v ISO formátu (YYYY-MM-DD), implicitně je použito aktuální datum

Autor: Pavel Šenovský
Verze: 0.1
Datum: 2025-06-20
"""

import configparser                                     # práce s konfiguračními soubory typu init
import os
import time
import argparse                                         # argumenty příkazového řádku
import csv                                              # zpracování CSV souborů
import pymysql.cursors                                  # MySQL
# následující žádek je dočasný hack v důlsedku chyby v implementaci knihovny transformers. Tato normálně funguje následovně
# from transformers import pipeline
# v posledních obsahuje bug (je nahlášený, ale ačkoliv je to pár měsíců není ještě opravený)
from transformers.pipelines import pipeline             # NLP
from atproto import Client, models                      # API BlueSky
from datetime import datetime, timedelta, timezone      # čas, datum, zóny

# společné funkce pro všechny moduly
from utils import check_config_ini

# Inicializace proměnných modelů
# TODO: refaktorovat do jiného modulu
rozpoznani_entit = None
detekce_dezinformaci = None
config = configparser.RawConfigParser()

def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global config
    config = check_config_ini() # kontrola config.ini
    # zpracování argumentů příkazové řádky
    parser = argparse.ArgumentParser(
                        prog='SocNetwork.py',
                        description='Program analysuje příspěvky ze sociálních sítí podle zadaných klíčových slov a časového vymezení a ukládá je do JSON souboru pro pozdější zpracování')
    parser.add_argument("-p", "--postJSON", help="soubor JSONL s příspěvky")
    parser.add_argument("-k", "--keywords", help="soubor CSV s klíčovými slovy (hashtagy)")
    parser.add_argument("-l", "--lang", help="jazyk oddělené čárkou, které se má vyhledávat (en, cs, sk), cs je výchozí")
    parser.add_argument("-od", "--since", help="datum, od kdy se mají vytěžovat příspěvky v ISO formátu (YYYY-MM-DD)")
    parser.add_argument("-do", "--until", help="datum, do kdy se mají vytěžovat příspěvky (včetně) v ISO formátu (YYYY-MM-DD)")
    args = parser.parse_args()
    if not args.postJSON  or not args.keywords:
        parser.print_help()
        exit()
    # T0D0:... je vyžadováno kvůli chybě v API BlueSky. V dokumentaci API je uvedeno, že stačí datum v ISO formátu, ale v praxi se jedná o časové razítko.
    # chyba je nahlášena, ale není opravena (přestože je to už rok) ... takže se jedná o workaround
    if not args.since:
        cas_limitu = datetime.now(timezone.utc) - timedelta(days=int(config["casove_limity"]["historie_dni"]))
        config.set("BlueSky", "since", cas_limitu.strftime("%Y-%m-%dT00:00:00.000Z"))
    else:
        config.set("BlueSky", "since", args.since)
    if not args.until:
        config.set("BlueSky", "until", datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:00.000Z"))
    else:
        config.set("BlueSky", "until", args.until)
    if not args.lang:
        config.set("BlueSky", "lang", "cs")
    else:
        config.set("BlueSky", "lang", args.lang)
    config.add_section("cesty")
    config.set("cesty", "json_vystup", args.postJSON)
    config.set("cesty", "keywords", args.keywords)

# TODO: refaktorovat do jiného modulu
def inicializovat_modely():
    """
    Iniciace modelů strojového učení
    """
    global rozpoznani_entit, detekce_dezinformaci
    # Definice předtrénovaných modelů pro analýzu textu
    MODEL_NAZEV_NER = "dbmdz/bert-large-cased-finetuned-conll03-english"        # entity
    MODEL_NAZEV_FAKE_NEWS = "facebook/bart-large-mnli"                          # dezinformace
    print("Inicializace modelů strojového učení.....")
    rozpoznani_entit = pipeline("ner", model=MODEL_NAZEV_NER, aggregation_strategy="simple")
    detekce_dezinformaci = pipeline("zero-shot-classification", model=MODEL_NAZEV_FAKE_NEWS)
    print("✅ Modely úspěšně inicializovány")

# TODO: refaktorovat do jiného modulu
def connect_to_db():
    """
    Připojí k databázi

    Parameters
    ----------
    config : dict
        konfigurační slovník.

    Returns
    -------
    conn : pymysql.connection
        připojení k databázi.
    """
    global config
    try:
        conn = pymysql.connect(host=config["databaze"]["host"],
                               user=config["databaze"]["user"],
                               password=config["databaze"]["password"],
                               database=config["databaze"]["dbname"],
                               port=int(config["databaze"]["port"]),
                               charset=config["databaze"]["charset"],
                               cursorclass=pymysql.cursors.DictCursor)
        return conn
    except Exception as e:
        print("❌ Chyba při připojení k databázi:", e)
        exit()



def nacti_klicova_slova():
    """
    Načte klíčová slova z souboru config['cesty']['keywords'].

    Returns
    -------
    keywords : list of str
        seznam klíčových slov
    """
    global config
    keywords = []
    csv_path = config['cesty']['keywords']
    if not os.path.exists(csv_path):
        print(f"❌ soubor se seznamem klíčových slove {csv_path} neexistuje.")
        exit()
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader) # Skip header
        for row in reader:
            if row:
                keywords.append(row[0])
    return keywords

# Hlavní funkce
def main():
    global config
    check_config() # kontrola konzistence config.ini

    klient = Client()
    profil = klient.login(config['BlueSky']['user'], config['BlueSky']['password'])
    print('Vítejte, ', profil.display_name)
    temata = nacti_klicova_slova()
    klic = " OR ".join(temata)
    lang = config['BlueSky']['lang'].split(",")
    vsechny_prispevky = []
    cursor = None

    print(f"Těžím příspěvky od: {config['BlueSky']['since']}")
    try:
        for l in lang:
            while True:
                params = models.AppBskyFeedSearchPosts.Params(
                    q = klic,
                    since = config['BlueSky']['since'],
                    until = config['BlueSky']['until'],
                    lang = l,
                    limit = 100,
                    cursor = cursor
                )
                vysledky = klient.app.bsky.feed.search_posts(params)
                vsechny_prispevky.extend(vysledky.posts)

                if not vysledky.cursor:
                    break # žádné další stránky

                cursor = vysledky.cursor
                time.sleep(int(config["casove_limity"]["zpozdeni_mezi_dotazy"]))

            print(f"✅ Příspěvky v {l} vytěženy")
            time.sleep(int(config["casove_limity"]["zpozdeni_mezi_dotazy"]))

        print("✅ všechny příspěvky vytěženy")
        # DEBUG: otestuj vyhledávání v soc síti - ulož výsledek do JSONL souboru
        with open(config['cesty']['json_vystup'], "w", encoding="utf-8") as f:
            for post in vsechny_prispevky:
                f.write(post.model_dump_json())
                f.write("\n")
        print(f"✅ ... a uloženy do souboru {config['cesty']['json_vystup']}")

    except Exception as e:
        print(f"❌ Chyba při vytěžování příspěvků: {e}")
        print(f"Detaily výjimky: {str(e)}")

if __name__ == "__main__":
    main()
