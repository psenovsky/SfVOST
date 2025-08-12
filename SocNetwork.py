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
Datum: 2025-06-20
"""

import argparse                                         # argumenty příkazového řádku
from src.BlueSky import BlueSky

bs = None

def check_config():
    """
    Provede kontrolu integrity konfiguračního souboru a nastavení odvozená z parametrů přikazové řádky a připraví konfigurační slovník pro další použití v aplikaci.
    """
    global bs
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

    try:
        bs = BlueSky(args.postJSON, args.keywords, args.lang, args.since, args.until)
    except Exception as e:
        print(f"❌ Chyba při inicializaci: {e}")
        print(f"Detaily výjimky: {str(e)}")
        exit()

# Hlavní funkce
def main():
    check_config() # kontrola konzistence config.ini
    bs.uloz_prispevky()

if __name__ == "__main__":
    main()
