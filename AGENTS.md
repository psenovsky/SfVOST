# SFVOST

## Introduction to the project

The project is used to perform analysis of the social media posts for purposes for VOST (Virtual Operation Support Team). Such teams are used during large-scale emergencies which require crisis management and long time to fully resolve them.

At present time the majority of the project is written in Python with data analysis part being implemented in RMarkdown (R programming language). The project supports:

- NER (NAmed Entity Recognition)
- sentiment analysis
- disinformation detection

for the cosial network posts.

Although this file is written in English, the project itself is Czech, so all labels, error messages, etc. visible by the user must be written in Czech.

## The plan

Dokončili jsme scrapovací nástroj `scraper.py`. Tento nástroj používáme pro doplnění některých chybějících informací v CSV souboru. Původně jsme CSV soubor (např. `data/Tornádo 2001_small.csv`) používali pro analýzu pomocí LLM ve skriptu `newton_one.py`. Scraper, ale produkuje jsonl formát. Potřebujeme upravit newton_one.py tak, aby bral i tento výstupní formát jako vstup. Bude potřeba upravit také výstupní formát jsonl ve newton_one.py, tak aby se použily nově přidaná pole.


