"""
Název: ner.py
Popis: Tento skript provádí analýzu pojmenovaných entit (NER) a seznam identifikovaných entit uloží do formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py nebo sentiment.py.

použití:
--------
    python ner.py -p <souborJSONL> -n <souborJSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -p, --postJSON souborJSONL - soubor JSON s příspěvky
- -n, --ner souborJSONL - soubor JSON s pojmenovanými entitami

Autor: Pavel Šenovský
Datum: 2025-07-07
"""
import configparser                                     # práce s konfiguračními soubory typu init
import os
import json                                             # zpracování JSON souborů
import argparse                                         # argumenty příkazového řádku

from ner_CZ import ner_CZ
from ner_BERT_EN import ner_BERT_EN

# společné funkce pro všechny moduly
from utils import check_config_ini

# iniciace globálních proměnných
config = configparser.RawConfigParser()

def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global config
    config = check_config_ini() # kontrola config.ini
    # zpracování argumentů příkazové řádky
    description = f'verze: {config.get("general", "version")}\nprovádí analýzu pojmenovaných entit (NER) a seznam identifikovaných entit uloží do formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py nebo sentiment.py.'
    parser = argparse.ArgumentParser(
                        prog='ner.py',
                        description=description,
                        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-p", "--postJSON", help="soubor JSONL s příspěvky")
    parser.add_argument("-n", "--ner", help="soubor JSONL s pojmenovanými entitament")
    args = parser.parse_args()
    if not args.postJSON  or not args.ner:
        parser.print_help()
        exit()
    if not os.path.exists(args.postJSON):
        print(f"❌ soubor s příspěvky {args.postJSON} neexistuje.")
        exit()
    config.add_section("cesty")
    config.set("cesty", "json_vystup", args.postJSON)
    config.set("cesty", "ner", args.ner)

def main():
    # inicializace konfigurace
    global config # analyza_sentimentu
    check_config() # kontrola konzistence config.ini
    # načti příspěvky ze souboru
    cesta_json = config.get("cesty", "json_vystup")

    # načtení JSON souboru s příspěvky
    obsah = []
    prispevky = 0
    preskoceno = 0
    bert_en = ner_BERT_EN()
    ner_cz = ner_CZ()
    with open(cesta_json, 'r', encoding='utf-8') as file:
        for line in file:
            prispevky = prispevky + 1
            if line.strip():  # přeskočit prázdné řádky
                try:
                    data = json.loads(line)
                    lang = data['record']['langs'][0] # první jazyk uvedený v příspěvku
                    if lang == 'en':
                        data['ner'] = bert_en.ner(data['record']['text'])
                    elif lang == ['cs', 'bg', 'pl', 'ru', 'uk']:
                        data['ner'] = ner_cz.ner(data['record']['text'])
                    else:
                        preskoceno = preskoceno + 1
                        print(f"❌ příspěvek v neznámém jazyce {lang}, přeskakuji řádek {line}")
                    obsah.append(data)
                except json.JSONDecodeError:
                    print(f"❌ Chyba při načítání příspěvku: {line}")

    if not obsah:
        print("⚠️ Varování: Žádné platné příspěvky nebyly načteny. Zkontrolujte soubor, který načítáte.")
        exit()

    cesta_ner = config.get("cesty", "ner")
    with open(cesta_ner, 'w', encoding='utf-8') as file:
        for obsahu in obsah:
            file.write(json.dumps(obsahu) + "\n")

    print(f"✅ uloženo do souboru {config['cesty']['ner']}")
    print(f"Zpracováno: {prispevky} příspěvků")
    print(f"Preskočeno: {preskoceno} příspěvků (z důvodu neznámého jazyka)")

if __name__ == "__main__":
    main()
