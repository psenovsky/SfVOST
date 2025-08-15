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

if __name__ == "__main__":
    main()
