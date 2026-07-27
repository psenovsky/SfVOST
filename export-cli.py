"""
Název: export-cli.py
Popis: Tento skript provádí konverzi příspěvků ze sociálních sítí z formátu JSONL do formátu Parquet (Apache Arrow).
       Parquet formát je optimalizovaný pro analytické účely a je vhodný pro načítání v R pomocí balíku arrow.

použití:
--------
    python export-cli.py -i <souborJSONL> -o <souborParquet>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -i, --input souborJSONL - vstupní soubor JSONL s příspěvky
- -o, --output souborParquet - výstupní soubor Parquet

Autor: Pavel Šenovský
Datum: 2026-07-27
"""
import argparse
import os
from src.models import nacti_prispevky_z_jsonl, uloz_prispevky_do_parquet


def main():
    description = (
        'Skript provádí konverzi příspěvků ze sociálních sítí z formátu JSONL '
        'do formátu Parquet (Apache Arrow). Parquet je optimalizovaný pro analytické '
        'účely a je vhodný pro načítání v R pomocí balíku arrow.'
    )
    parser = argparse.ArgumentParser(
        prog='export-cli.py',
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-i", "--input", help="vstupní soubor JSONL s příspěvky")
    parser.add_argument("-o", "--output", help="výstupní soubor Parquet")
    args = parser.parse_args()

    if not args.input or not args.output:
        parser.print_help()
        exit()

    if not os.path.exists(args.input):
        print(f"❌ vstupní soubor {args.input} neexistuje.")
        exit()

    print(f"Načítám příspěvky z souboru {args.input}...")
    prispevky = nacti_prispevky_z_jsonl(args.input)
    if not prispevky:
        print("⚠️ Žádné příspěvky nebyly načteny.")
        exit()

    print(f"Ukládám {len(prispevky)} příspěvků do Parquet souboru {args.output}...")
    uloz_prispevky_do_parquet(prispevky, args.output)


if __name__ == "__main__":
    main()
