"""
Název: ner-cli.py
Popis: Tento skript provádí analýzu pojmenovaných entit (NER) a seznam identifikovaných entit uloží do formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py nebo sentiment.py.

použití:
--------
    python ner-cli.py -p <souborJSONL> -n <souborJSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -p, --postJSON souborJSONL - soubor JSON s příspěvky
- -n, --ner souborJSONL - soubor JSON s pojmenovanými entitami

Autor: Pavel Šenovský
Datum: 2025-07-07
"""
import argparse                                         # argumenty příkazového řádku
from src.ner import ner

nr = None

def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global nr
    # zpracování argumentů příkazové řádky
    description = f'Skript provádí analýzu pojmenovaných entit (NER) a seznam identifikovaných entit uloží do formátu JSONL. Soubor ve správném formátu je možno získat pomocí skriptu SocNetwork.py nebo sentiment.py.'
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
    try:
        nr = ner(args.postJSON, args.ner)
    except Exception as e:
        print(f"❌ Chyba při inicializaci: {e}")
        print(f"Detaily výjimky: {str(e)}")
        exit()

def main():
    global nr
    check_config() # kontrola konzistence config.ini
    nr.uloz_prispevky()

    # # načti příspěvky ze souboru
    # cesta_json = config.get("cesty", "json_vystup")

    # # načtení JSON souboru s příspěvky
    # obsah = []
    # prispevky = 0
    # preskoceno = 0
    # bert_en = ner_BERT_EN()
    # ner_cz = ner_CZ()
    # with open(cesta_json, 'r', encoding='utf-8') as file:
    #     for line in file:
    #         prispevky = prispevky + 1
    #         if line.strip():  # přeskočit prázdné řádky
    #             try:
    #                 data = json.loads(line)
    #                 lang = data['record']['langs'][0] # první jazyk uvedený v příspěvku
    #                 if lang == 'en':
    #                     data['ner'] = bert_en.ner(data['record']['text'])
    #                 elif lang == ['cs', 'bg', 'pl', 'ru', 'uk']:
    #                     data['ner'] = ner_cz.ner(data['record']['text'])
    #                 else:
    #                     preskoceno = preskoceno + 1
    #                     print(f"❌ příspěvek v neznámém jazyce {lang}, přeskakuji řádek {line}")
    #                 obsah.append(data)
    #             except json.JSONDecodeError:
    #                 print(f"❌ Chyba při načítání příspěvku: {line}")

    # if not obsah:
    #     print("⚠️ Varování: Žádné platné příspěvky nebyly načteny. Zkontrolujte soubor, který načítáte.")
    #     exit()

    # cesta_ner = config.get("cesty", "ner")
    # with open(cesta_ner, 'w', encoding='utf-8') as file:
    #     for obsahu in obsah:
    #         file.write(json.dumps(obsahu) + "\n")

    # print(f"✅ uloženo do souboru {config['cesty']['ner']}")
    # print(f"Zpracováno: {prispevky} příspěvků")
    # print(f"Preskočeno: {preskoceno} příspěvků (z důvodu neznámého jazyka)")

if __name__ == "__main__":
    main()
