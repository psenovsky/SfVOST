"""
Název: sentiment.py
Popis: Tento skript provádí analýzu příspěvků ze sítě BlueSky uložených ve formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py

použití:
--------
    python sentiment.py -p <souborJSONL> -s <souborJSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -p, --postJSON souborJSONL - soubor JSON s příspěvky
- -s, --sentiment souborJSONL - soubor JSON s určením sentimentu příspěvků

Autor: Pavel Šenovský
Datum: 2025-07-07
"""
import configparser                                     # práce s konfiguračními soubory typu init
import os
import json                                             # zpracování JSON souborů
import argparse                                         # argumenty příkazového řádku
import regex as re                                      # regulární výrazy s Unicode podporou

# společné funkce pro všechny moduly
from utils import check_config_ini
from sentiment_BERT_multi import sentiment_BERT_multi
from sentiment_Czert_B import sentiment_Czert_B

# iniciace globálních proměnných
analyza_sentimentu = None
config = configparser.RawConfigParser()

def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global config
    config = check_config_ini() # kontrola config.ini
    # zpracování argumentů příkazové řádky
    description = f'verze: {config.get("general", "version")}\nProgram analysuje příspěvky ze sociálních sítí poskytnuté v JSONL souboru a odhadne sentiment autora příspěvku na bázi modelu strojového učení.'
    parser = argparse.ArgumentParser(
                        prog='sentiment.py',
                        description=description,
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-p", "--postJSON", help="soubor JSONL s příspěvky")
    parser.add_argument("-s", "--sentiment", help="soubor JSONL s určením sentimentu příspěvků")
    args = parser.parse_args()
    if not args.postJSON  or not args.sentiment:
        parser.print_help()
        exit()
    if not os.path.exists(args.postJSON):
        print(f"❌ soubor s příspěvky {args.postJSON} neexistuje.")
        exit()
    config.add_section("cesty")
    config.set("cesty", "json_vystup", args.postJSON)
    config.set("cesty", "sentiment", args.sentiment)


def clean_text(text):
    """
    Provede vyčištění textu, odstraní speciální znaky, emotikony, atd. a převede na malá písmena.
    """
    text = re.sub(r'[^\p{L}\s]', '', text)
    return text.lower()

# Hlavní funkce
def main():
    global config # analyza_sentimentu
    check_config() # kontrola konzistence config.ini
    # načti příspěvky ze souboru
    cesta_json = config.get("cesty", "json_vystup")

    # načtení JSON souboru s příspěvky
    obsah = []
    prispevky = 0
    preskoceno = 0
    bertMulti = sentiment_BERT_multi()
    czertB = sentiment_Czert_B()
    with open(cesta_json, 'r', encoding='utf-8') as file:
        for line in file:
            prispevky = prispevky + 1
            if line.strip():  # přeskočit prázdné řádky
                try:
                    data = json.loads(line)
                    t = clean_text(data['record']['text'])
                    lang = data['record']['langs'][0] # první jazyk uvedený v příspěvku
                    if lang in ['en', 'nl', 'de', 'fr', 'it', 'es']:
                        data['sentiment'] = bertMulti.sentiment(t)
                    elif lang == 'cs':
                        data['sentiment'] = czertB.sentiment(t)
                    else:
                        preskoceno = preskoceno + 1
                        print(f"❌ příspěvek v neznámém jazyce {lang}, přeskakuji řádek {line}")
                    obsah.append(data)
                except json.JSONDecodeError:
                    print(f"❌ Chyba při načítání příspěvku: {line}")

    if not obsah:
        print("⚠️ Varování: Žádné platné příspěvky nebyly načteny. Zkontrolujte soubor, který načítáte.")
        exit()

    with open(config['cesty']['sentiment'], "w", encoding="utf-8") as f:
        for o in obsah:
            f.write(json.dumps(o))
            f.write("\n")

    print(f"✅ uloženo do souboru {config['cesty']['sentiment']}")
    print(f"Zpracováno: {prispevky} příspěvků")
    print(f"Preskočeno: {preskoceno} příspěvků (z důvodu neznámého jazyka)")

if __name__ == "__main__":
    main()
