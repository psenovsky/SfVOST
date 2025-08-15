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
Datum: 2025-08-15
"""
import argparse                                         # argumenty příkazového řádku
from src.sentiment import sentiment


# iniciace globálních proměnných
sen = None

def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global sen
    # zpracování argumentů příkazové řádky
    description = f'Program analysuje příspěvky ze sociálních sítí poskytnuté v JSONL souboru a odhadne sentiment autora příspěvku na bázi modelu strojového učení.'
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
    try:
        sen = sentiment(args.postJSON, args.sentiment)
    except Exception as e:
        print(f"❌ Chyba při inicializaci: {e}")
        print(f"Detaily výjimky: {str(e)}")
        exit()

# Hlavní funkce
def main():
    global sen
    check_config() # kontrola konzistence config.ini
    sen.uloz_prispevky()

if __name__ == "__main__":
    main()
