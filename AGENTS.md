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

Dokončujeme práci na `scrapper.py`. Je potřeba udělat drobnou úpravu zohledňující změnu v datovém souboru `data/Tornádo 2021_spojené_small.csv`. V tomto souboru  přibyl nový sloupec `Manuálně`, který je potřeba exportovat také do výstupního jsonl souboru. Hodnotu je možno pouze převzít, není nutno ji upravovat.


