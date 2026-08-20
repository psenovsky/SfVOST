# -*- coding: utf-8 -*-

"""Užitečné helper funkce pro newton_one – data parsing a progress bar."""

from datetime import datetime


from src.newton_one.models import UNICODE_WHITESPACE


def parse_datum(date_str):
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
    for fmt in ("%Y-%m-%d", "%d.%m.%Y %H:%M"):
        try:
            datetime.strptime(date_str, fmt)
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Pokud žádný formát nevyfunčí, vrátíme původní hodnotu
    return date_str


def strip_unicode_whitespace(text):
    """Odstraní Unicode whitespace znaky z textu."""
    if not text or not isinstance(text, str):
        return text
    return "".join(ch for ch in text if ch not in UNICODE_WHITESPACE).strip()


def progress_bar(i, total):
    """Vytvoří progress bar s naplněnou šířkou 50 znaků."""
    percent = (i + 1) / total * 100
    filled = int(percent / 2)
    bar = "#" * filled + "-" * (50 - filled)
    return f"\r{bar} {i+1}/{total} ({percent:.0f}%)\n", percent
