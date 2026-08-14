# -*- coding: utf-8 -*-

"""
Název: newton_one.py
Popis: CLI utilita pro načtení NewtonOne CSV souboru a konverzi do JSONL formátu pro následnou analýzu.

použití:
--------
    python newton_one.py -c <cesta_k_CSV> -o <cesta_k_JSONL>

Parametry:
----------
- -h, --help  - zobrazí nápovědu a skončí
- -c, --csv   - cesta k semicolon-delimited CSV souboru (povinné)
- -o, --output - výstupní JSONL soubor (povinný)

Autor: Pavel Šenovský
Datum: 2026-08-14
"""
import argparse                                              # argumenty příkazového řádku
import csv                                                    # čtení CSV souborů
import json                                                   # serializace JSON
import os                                                     # operace se systémem
from datetime import datetime                                 # práce s daty


# =============================================================================
# Konstanty
# =============================================================================

CSV_SEP = ";"                                                 # odliovník sloupců v NewtonOne CSV
ENCODING = "utf-8"                                            # kódování vstupního souboru
JSONL_ENCODING = "utf-8"                                      # kódování výstupního souboru
OUTPUT_DELIMITER = "\t"                                       # oddělovač klíčů v JSON (pro determinismus)


# Sloupci, které budeme extrahovat z CSV
SLoupce = [
    {"nazev": "Kód článku",     "typ": str},
    {"nazev": "Datum publikování", "typ": str},
    {"nazev": "Název",          "typ": str},
    {"nazev": "Zdroj",           "typ": str},
    {"nazev": "Země",            "typ": str},
    {"nazev": "Typ média",       "typ": str},
    {"nazev": "Anotace",         "typ": str},
    {"nazev": "Plné znění",      "typ": str},
    {"nazev": "Typ zprávy",      "typ": str},
    {"nazev": "Sentiment",       "typ": str},
    {"nazev": "Dosah",           "typ": str},
]


# =============================================================================
# Funkce
# =============================================================================

def parse_datum(date_str: str) -> str | None:
    """
    Zkusí přeměnit řetězec na formát YYYY-MM-DD.

    Parameters
    ----------
    date_str : str
        Datum v libovolném formátu (např. '25.06.2021 00:00').

    Vrací
    -----
    str nebo None
        Formátované datum YYYY-MM-DD, pokud je parsovatelné; jinak původní řetězec.
    """
    if not date_str or not isinstance(date_str, str):
        return date_str

    date_str = date_str.strip()
    for formát in ("%Y-%m-%d", "%d.%m.%Y %H:%M"):
        try:
            datetime.strptime(date_str, formát)
            return datetime.strptime(date_str, formát).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Pokud žádný formát nevyfunčí, vrátíme původní hodnotu
    return date_str


def nacti_csv(cesta_csv: str) -> list[dict[str, str]]:
    """
    Načte semicolon-delimited CSV soubor a vrací seznam slovníků.

    Parameters
    ----------
    cesta_csv : str
        Cesta k vstupnímu CSV souboru.

    Vrací
    -----
    list[dict[str, str]]
        Seznam řádků jako slovníky s klíči odpovídajícími názvům sloupců v CSV.
    """
    if not os.path.exists(cesta_csv):
        print(f"❌ Vstupní CSV soubor neexistuje: {cesta_csv}")
        return []

    radky = []
    with open(cesta_csv, "r", encoding=ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=CSV_SEP)
        for jazyk in reader:
            if not jazyk or all(not v.strip() for v in jazyk.values()):
                continue
            radky.append(jazyk)

    print(f"✅ Načteno {len(radky)} řádků z souboru {cesta_csv}")
    return radky


def pretvorit_radku(radka: dict[str, str]) -> dict[str, str]:
    """
    Přetvoří jeden řádek CSV na JSON objekt podle definice SLoupce.

    Parameters
    ----------
    radka : dict[str, str]
        Jeden řádek z CSV (klíče jsou názvy sloupců).

    Vrací
    -----
    dict[str, str]
        Přetvořený řádek s vypsáním hodnot a formátováním dat.
    """
    vysledek = {}
    for sloupec in SLoupce:
        nazev = sloupec["nazev"]
        hodnota = radka.get(nazev, "").strip()
        if not hodnota:
            hodnota = ""

        # Datum publikování formátujeme na YYYY-MM-DD
        if nazev == "Datum publikování":
            hodnota = parse_datum(hodnota) or hodnota

        vysledek[nazev] = hodnota

    return vysledek


def ulozit_jsonl(radky: list[dict[str, str]], cesta_output: str) -> int:
    """
    Uloží řádky do JSONL souboru se sorted keys pro determinismus.

    Parameters
    ----------
    radky : list[dict[str, str]]
        Seznam přetvořených řádků.
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.

    Vrací
    -----
    int
        Počet zapsaných řádků.
    """
    if not radky:
        print("⚠️ Žádné data pro zápis.")
        return 0

    # Zkontrolovat, zda soubor již existuje
    if os.path.exists(cesta_output):
        velkost_input = os.path.getsize(cesta_output)
        if velkost_input == 0:
            print(f"⚠️ Výstupní soubor {cesta_output} je prázdný, přepsu ho.")
        else:
            print(f"⚠️ Výstupní soubor {cesta_output} již existuje ({velkost_input} B). Přepisuji ho.")

    # Uložit
    count = 0
    with open(cesta_output, "w", encoding=JSONL_ENCODING) as f:
        for radka in radky:
            json_str = json.dumps(radka, ensure_ascii=False, sort_keys=True)
            f.write(json_str + "\n")
            count += 1

            # Progress bar (50 znaků)
            if count % 10 == 0 or count == len(radky):
                percent = count / len(radky) * 100
                filled = int(percent / 2)
                bar = "█" * filled + "░" * (50 - filled)
                print(f"\r{bar} {count}/{len(radky)} ({percent:.0f}%)", end="")

    print()  # nový řádek po progress baru
    print(f"✅ Zapsáno {count} řádků do souboru {cesta_output}")
    return count


# =============================================================================
# Hlavní funkce
# =============================================================================

def main():
    """Hlavní vstupní bod skriptu."""
    description = (
        "CLI utilita pro načtení NewtonOne CSV souboru a konverzi do JSONL formátu"
        " pro následnou analýzu."
    )
    parser = argparse.ArgumentParser(
        prog='newton_one.py',
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-c", "--csv", help="cesta k semicolon-delimited CSV souboru")
    parser.add_argument("-o", "--output", help="výstupní JSONL soubor")

    args = parser.parse_args()

    if not args.csv or not args.output:
        parser.print_help()
        exit(0)

    # Kontrola existenci vstupního souboru
    if not os.path.exists(args.csv):
        print(f"❌ Vstupní CSV soubor {args.csv} neexistuje.")
        exit(1)

    # Načtení dat
    radky = nacti_csv(args.csv)
    if not radky:
        print("⚠️ Žádné řádky k zpracování.")
        exit(0)

    # Přetvoření řádků
    vysledky = [pretvorit_radku(r) for r in radky]

    # Zápis do JSONL
    ulozit_jsonl(vysledky, args.output)


if __name__ == "__main__":
    main()
