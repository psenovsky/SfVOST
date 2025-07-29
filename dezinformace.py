"""
Název: dezinformace.py
Popis: Tento skript provádí analýzu příspěvků na dezinformace. Skript předpokládá vstup ve formátu produkovaném SocNetwork.py s nebo bez sentimentu a NER.

použití:
--------
    python dezinformace.py -p <souborJSONL> -d <souborJSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -p, --postJSON souborJSONL - soubor JSON s příspěvky
- -d, --desinformaceJSON souborJSONL - soubor JSON s pojmenovanými identifikace [fake/reliable]

Autor: Pavel Šenovský
Datum: 2025-07-07
"""
import configparser                                     # práce s konfiguračními soubory typu init
import os
import json                                             # zpracování JSON souborů
import argparse                                         # argumenty příkazového řádku
# následující žádek je dočasný hack v důlsedku chyby v implementaci knihovny transformers. Tato normálně funguje následovně
# from transformers import pipeline
# v posledních obsahuje bug (je nahlášený, ale ačkoliv je to pár měsíců není ještě opravený)
from transformers.pipelines import pipeline             # NLP

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
    description = f'verze: {config.get("general", "version")}\nprovádí analýzu příspěvků na dezinformace. Skript předpokládá vstup ve formátu produkovaném SocNetwork.py s nebo bez sentimentu a NER.'
    parser = argparse.ArgumentParser(
                        prog='dezinformace.py',
                        description=description,
                        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-p", "--postJSON", help="soubor JSONL s příspěvky")
    parser.add_argument("-d", "--dezinformaceJSON", help="soubor JSONL s rozlišením fake/reliable")
    args = parser.parse_args()
    if not args.postJSON  or not args.dezinformaceJSON:
        parser.print_help()
        exit()
    if not os.path.exists(args.postJSON):
        print(f"❌ soubor s příspěvky {args.postJSON} neexistuje.")
        exit()
    config.add_section("cesty")
    config.set("cesty", "json_vystup", args.postJSON)
    config.set("cesty", "dezinformace", args.dezinformaceJSON)

def main():
    # inicializace konfigurace
    global config # analyza_sentimentu
    check_config() # kontrola konzistence config.ini
    detekce_dezinformaci = pipeline("zero-shot-classification", model = "facebook/bart-large-mnli")
    labels = ["fake news", "reliable news"]
    # načti příspěvky ze souboru
    cesta_json = config.get("cesty", "json_vystup")
    # načtení JSON souboru s příspěvky
    obsah = []
    prispevky = 0
    with open(cesta_json, 'r', encoding='utf-8') as file:
        for line in file:
            prispevky = prispevky + 1
            if line.strip():  # přeskočit prázdné řádky
                try:
                    data = json.loads(line)
                    t = detekce_dezinformaci(data['record']['text'], candidate_labels = labels)
                    data['dezinformace'] = {}
                    data['dezinformace']['label'] = t['labels'][0]
                    data['dezinformace']['score'] = t['scores'][0]
                    obsah.append(data)
                except json.JSONDecodeError:
                    print(f"❌ Chyba při načítání příspěvku: {line}")

    if not obsah:
        print("⚠️ Varování: Žádné platné příspěvky nebyly načteny. Zkontrolujte soubor, který načítáte.")
        exit()

    cesta_ner = config.get("cesty", "dezinformace")
    with open(cesta_ner, 'w', encoding='utf-8') as file:
        for obsahu in obsah:
            file.write(json.dumps(obsahu) + "\n")

    print(f"✅ uloženo do souboru {config['cesty']['dezinformace']}")
    print(f"Zpracováno: {prispevky} příspěvků")
    # print(f"Preskočeno: {preskoceno} příspěvků (z důvodu neznámého jazyka)")

if __name__ == "__main__":
    main()
