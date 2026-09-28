# -*- coding: utf-8 -*-

"""Načtení CSV a zápis JSONL – data I/O pro newton_one."""

import csv as _csv
import json
import os
import shutil


from src.newton_one.models import (
    CSV_SEP,
    ENCODING,
    JSONL_ENCODING,
    OUTPUT_DELIMITER,
    SLoupce,
)
from src.newton_one.utils import parse_datum, strip_unicode_whitespace


def nacti_csv(cesta_csv):
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
        reader = _csv.DictReader(f, delimiter=CSV_SEP)
        for radek in reader:
            if not radek or all(not v.strip() for v in radek.values()):
                continue
            radky.append(radek)

    print(f"✅ Načteno {len(radky)} řádků z souboru {cesta_csv}")
    return radky


def pretvorit_radku(radka):
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
        hodnota = radka.get(nazev, "")

        # Strhání mezernat ze všech hodnot (včetně Unicode whitespace)
        if sloupec.get("strip_space"):
            hodnota = strip_unicode_whitespace(hodnota)

        if not hodnota:
            hodnota = ""

        if nazev == "URL článku" and sloupec.get("strip_space"):
            hodnota = strip_unicode_whitespace(hodnota)

        # Datum publikování formátujeme na YYYY-MM-DD
        if nazev == "Datum publikování":
            hodnota = parse_datum(hodnota) or hodnota

        # Dosah → integer
        if nazev == "Dosah" and sloupec.get("typ") == int:
            try:
                hodnota = int(float(hodnota))  # float→int pro případ desetinných čísel
            except (ValueError, TypeError):
                hodnota = ""

        vysledek[nazev] = hodnota

    return vysledek


def nacti_jsonl(cesta_jsonl):
    """
    Načte JSONL soubor (např. výstup scraperu) a vrací seznam slovníků.

    Záznamy jsou považovány za již přetvořená data (stejný formát jako výstup
    pretvorit_radku), proto se neaplikují žádné další transformace – vrátí se
    tak přesně to, co bylo v souboru uloženo.

    Parameters
    ----------
    cesta_jsonl : str
        Cesta k vstupnímu JSONL souboru.

    Vrací
    -----
    list[dict]
        Seznam řádků z JSONL. Prázdný seznam, pokud soubor neexistuje nebo je prázdný.
    """
    if not os.path.exists(cesta_jsonl):
        print(f"❌ Vstupní JSONL soubor neexistuje: {cesta_jsonl}")
        return []

    radky = []
    with open(cesta_jsonl, "r", encoding=JSONL_ENCODING) as f:
        for cislo_radky, radek in enumerate(f, start=1):
            radek = radek.strip()
            if not radek:
                continue
            try:
                obj = json.loads(radek)
            except json.JSONDecodeError as exc:
                print(f"⚠️ Chyba při čtení řádku {cislo_radky} v souboru {cesta_jsonl}: {exc}")
                continue
            if isinstance(obj, dict):
                radky.append(obj)

    print(f"✅ Načteno {len(radky)} řádků z JSONL souboru {cesta_jsonl}")
    return radky


def _retezec(hodnota):
    """Bezpečně převede hodnotu na řetězec (None → prázdný řetězec)."""
    if hodnota is None:
        return ""
    return hodnota if isinstance(hodnota, str) else str(hodnota)


def kod_radku(radka):
    """
    Vrátí identifikátor záznamu.

    Parameters
    ----------
    radka : dict
        Jeden záznam (slovník načtený z CSV nebo JSONL).

    Vrací
    -----
    str
        Hodnota sloupce 'Kód článku' (případně 'Kódčlánku'), jinak prázdný řetězec.
    """
    return _retezec(radka.get("Kód článku")) or _retezec(radka.get("Kódčlánku"))


def text_pro_analyzu(radka):
    """
    Vrátí text, který se posílá k LLM analýze: 'Plné znění', jinak 'Anotace'.

    Parameters
    ----------
    radka : dict
        Jeden záznam (slovník načtený z CSV nebo JSONL).

    Vrací
    -----
    str
        Text k analýze, prázdný řetězec pokud záznam žádný text neobsahuje.
    """
    plne_znani = _retezec(radka.get("Plné znění"))
    if plne_znani:
        return plne_znani
    return _retezec(radka.get("Anotace")).strip()


def chybi_llm_analyza(radka):
    """
    Rozhodne, zda záznam ve výstupním JSONL stále vyžaduje LLM analýzu.

    Za hotový se považuje záznam s neprázdným 'sentiment_LLM' (LLM analýza
    skutečně proběhla) i záznam bez jakéhokoli textu (analyzovat není co,
    jinak by se znovu zpracoval při každém běhu). Záznam, který má text,
    ale prázdné 'sentiment_LLM', je selhání LLM analýzy a musí se znovu
    zpracovat.

    Parameters
    ----------
    radka : dict
        Jeden záznam z výstupního JSONL.

    Vrací
    -----
    bool
        True, pokud je nutné záznam znovu analyzovat.
    """
    return bool(text_pro_analyzu(radka)) and not _retezec(radka.get("sentiment_LLM")).strip()


def precteni_stav_vystupu(cesta_output):
    """
    Načte stav výstupního JSONL pro navázání (resume) – soubor se nemění.

    Parameters
    ----------
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.

    Vrací
    -----
    dict
        {'hotove_kody': set, 'chybi_llm_kody': set, 'duplikaty': int, 'poskozeno': int}
        'hotove_kody' – kódy, které už nelze znovu zpracovat, 'chybi_llm_kody' – kódy
        záznamů, na kterých selhala LLM analýza, 'duplikaty' – počet opakovaných kódů,
        'poskozeno' – počet nečitelných řádků (částečný zápis po přerušení běhu).
    """
    stav = {"hotove_kody": set(), "chybi_llm_kody": set(), "duplikaty": 0, "poskozeno": 0}
    if not os.path.exists(cesta_output):
        return stav

    videne_kody = set()
    with open(cesta_output, "r", encoding=JSONL_ENCODING) as f:
        for radek in f:
            radek = radek.strip()
            if not radek:
                continue
            try:
                obj = json.loads(radek)
            except json.JSONDecodeError:
                stav["poskozeno"] += 1
                continue  # částečně zapsaný řádek po přerušení – nečitelný
            if not isinstance(obj, dict):
                stav["poskozeno"] += 1
                continue
            kod = kod_radku(obj)
            if kod and kod in videne_kody:
                stav["duplikaty"] += 1
            elif kod:
                videne_kody.add(kod)
            if chybi_llm_analyza(obj):
                if kod:
                    stav["chybi_llm_kody"].add(kod)
            elif kod:
                stav["hotove_kody"].add(kod)

    return stav


def opravit_vystup(cesta_output, zaloha=True):
    """
    Vyčistí výstupní JSONL – odstraní záznamy bez úspěšné LLM analýzy a duplicity.

    Záznamy, na kterých selhala LLM analýza, se odstraní, aby po opravě nevznikly
    duplicity – zpracovaný záznam se totiž průběžně doplní na konec souboru.
    Záznamy bez textu zůstávají zachovány, protože analyzovat je není co.

    Soubor se přepíše atomicky (dočasný soubor + os.replace) a před přepisem
    se uloží záloha '<cesta_output>.bak'. Pokud není co opravovat, soubor
    se vůbec nepřepisuje.

    Parameters
    ----------
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.
    zaloha : bool
        Zda před přepisem vytvořit zálohu původního souboru.

    Vrací
    -----
    dict
        {'bez_llm': int, 'duplikaty': int, 'poskozeno': int, 'zapsano': int}
    """
    vysledek = {"bez_llm": 0, "duplikaty": 0, "poskozeno": 0, "zapsano": 0}
    if not os.path.exists(cesta_output):
        return vysledek

    radky = []
    zapsane_kody = set()
    with open(cesta_output, "r", encoding=JSONL_ENCODING) as f:
        for radek in f:
            radek = radek.strip()
            if not radek:
                continue
            try:
                obj = json.loads(radek)
            except json.JSONDecodeError:
                vysledek["poskozeno"] += 1
                continue
            if not isinstance(obj, dict):
                vysledek["poskozeno"] += 1
                continue
            if chybi_llm_analyza(obj):
                vysledek["bez_llm"] += 1
                continue
            kod = kod_radku(obj)
            if kod and kod in zapsane_kody:
                vysledek["duplikaty"] += 1
                continue
            if kod:
                zapsane_kody.add(kod)
            radky.append(radek)
            vysledek["zapsano"] += 1

    if not (vysledek["bez_llm"] or vysledek["duplikaty"] or vysledek["poskozeno"]):
        return vysledek  # soubor je čistý – zbytečně ho nepřepisujeme

    if zaloha:
        shutil.copy2(cesta_output, cesta_output + ".bak")

    docasny = cesta_output + ".tmp"
    try:
        with open(docasny, "w", encoding=JSONL_ENCODING) as f:
            for radek in radky:
                f.write(radek + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(docasny, cesta_output)
    except OSError as exc:
        if os.path.exists(docasny):
            os.remove(docasny)
        print(f"❌ Výstupní soubor se nepodařilo opravit: {exc}")
        raise

    return vysledek


def ulozit_radku_jsonl(radka, cesta_output):
    """
    Dopíše jeden záznam na konec JSONL souboru (průběžné ukládání).

    Soubor se otevírá v append režimu, takže existující data nejsou přepsána.
    Počítačový buffer je po zápisu vyprázdněn pro odolnost proti přerušení.

    Parameters
    ----------
    radka : dict[str, str]
        Přetvořený řádek (musí obsahovat identifikátor sloupce 'Kód článku').
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.

    Vrací
    -----
    None
    """
    json_str = json.dumps(radka, ensure_ascii=False, sort_keys=True)
    with open(cesta_output, "a", encoding=JSONL_ENCODING) as f:
        f.write(json_str + "\n")
        f.flush()


def ulozit_jsonl(radky, cesta_output):
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
        if velkost_input != 0:
            print(f"⚠️ Výstupní soubor {cesta_output} již existuje ({velkost_input} B). Přepisuji ho.")

    # Uložit
    count = 0
    with open(cesta_output, "w", encoding=JSONL_ENCODING) as f:
        for radka in radky:
            json_str = json.dumps(radka, ensure_ascii=False, sort_keys=True)
            f.write(json_str + "\n")
            count += 1

    return count
