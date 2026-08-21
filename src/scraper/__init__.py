# -*- coding: utf-8 -*-

"""Modul scraper – načítání plných textů článků z URL (Phase 2)."""

from src.scraper.article_fetcher import (
    nacit_artikl,
    nacit_batch_artikul,
    nacti_z_ukazku_csv,
)

__all__ = [
    "nacit_artikl",
    "nacit_batch_artikul",
    "nacti_z_ukazku_csv",
]
