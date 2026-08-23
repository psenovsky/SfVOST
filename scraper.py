# -*- coding: utf-8 -*-

"""Runner skript pro scraper utility (Phase 3)."""

import argparse
import os


from src.newton_one.data_io import nacti_csv, pretvorit_radku, ulozit_jsonl
from src.scraper.article_fetcher import nacti_z_ukazku_csv


def main():
    """Hlavní vstupní bod skriptu."""
    description = (
        "CLI utilita pro načtení CSV s URL článků a získání plných textů."
    )
    parser = argparse.ArgumentParser(
        prog='scraper',
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-c", "--csv", help="cesta k CSV souboru se sloupcem 'URL článku'")
    parser.add_argument("-o", "--output", help="výstupní JSONL soubor")

    args = parser.parse_args()

    if not args.csv or not args.output:
        parser.print_help()
        exit(0)

    # Načtení článků z URL
    vysledky = nacti_z_ukazku_csv(args.csv)
    if not vysledky:
        print("⚠️ Žádné data pro zápis.")
        exit(0)

    # Zápis do JSONL (stejný formát jako newton_one.py)
    ulozit_jsonl(vysledky, args.output)


if __name__ == "__main__":
    main()
