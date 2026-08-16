"""
Název: config_loader.py
Popis: Modul pro čtení a přístup k hodnotám v config.ini
       s podporou fallbacku (fallback = hodnota použita pokud klíč neexistuje).

Autor: Pavel Šenovský
Datum: 2026-08-15
"""

import configparser
import os


class ConfigLoader:
    """Zábalí configparser a poskytuje jednoduchý přístup k hodnotám s fallbacky."""

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            project_root = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(project_root, "config.ini")
        self._path = config_path
        self._config = configparser.RawConfigParser()
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"❌ Konfigurační soubor neexistuje: {config_path}")
        self.read(config_path)

    def read(self, path: str | None = None):
        """Načte config.ini z dané cesty."""
        if path is None:
            path = self._path
        self._config.read(path)

    def get_config(self, section: str, key: str, fallback: str = "") -> str:
        """
        Vytáhne hodnotu klíče ze sekce. Pokud neexistuje vrátí fallback.

        Parameters
        ----------
        section : str
            Název sekce (např. 'newton_one').
        key : str
            Klíč v dané sekci.
        fallback : str
            Hodnota vrácená pokud klíč nebo sekce neexistuje.

        Vrací
        -----
        str
        """
        if section not in self._config:
            return fallback
        try:
            value = self._config.get(section, key)
            return value.strip()
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Vytáhne celoevropskou hodnotu."""
        val = self.get_config(section, key, fallback=str(fallback))
        try:
            return int(val)
        except ValueError:
            return fallback

    def exists(self, section: str, key: str = "") -> bool:
        """Zkontroluje zda sekce a případně klíč existují."""
        if section not in self._config:
            return False
        if key == "":
            return True
        try:
            self._config.get(section, key)
            return True
        except (configparser.NoSectionError, configparser.NoOptionError):
            return False

    def sections(self) -> list[str]:
        """Vrátí seznam všech sekcí v konfiguračním souboru."""
        return self._config.sections()


# Globální instance pro jednoduchý import
_config_instance = None


def get_config():
    """Vrátí globální instanci ConfigLoader (pro starší kód)."""
    global _config_instance
    if _config_instance is None:
        project_root = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(project_root, "config.ini")
        _config_instance = ConfigLoader(config_path)
    return _config_instance
