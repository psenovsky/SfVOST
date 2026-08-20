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

Pracujeme na části projektu, která se věnuje analýze příspěvků získaných pomocí služby monitoringu médií NewtonOne (stávající verze analýzy je v `newton_one.py`). Vždy se snažíme postupovat po relativně malých částech problémů (fázích), které řešíme postupně. Vždy vyřešíme jednu, tu pak odladíme a postupujeme dále.

Testovací data jsou dostupná v `data/Tornádo 2021_small.csv`. Při použití nástrojů přístupných si dej pozor na cestu - obsahuje mezeru, název je proto potřeba obalit do uvozovek tak, aby to v bash fungovalo. Dočasné a testovací soubory můžeš dát také do složky `tmp` ve složce projektu.

- [x] Fáze 1: Reorganizace `newton_one.py`
- [x] Fáze 2: Příprava pro webscrapper


### Fáze 1: Reorganizace `newton_one.py`

Dosud jsme analýzu řešili jedním skriptem, ukážalo se ale, že celý proces bude složitější a nemá proto smysl abychom kód drželi v jednom souboru. Vytvoř proto složku `newton_one` v složce `src` a to ní budeme refaktorovat stávající kód z `newton_one.py`. V root projektu by měl zůstat runner skript. Parametry příkazové řádky tohoto skriptu by prozatím tůstaly stejné.

Analyzuj obsah `newton_one.py`. Navrhni jak reorganizovat tento soubor a plán si nech schválit.

### Fáze 2: Příprava pro webscrapper

Naším celovým cílem, ke kterému dojdeme v dalších etapách vývoje, je návrh utility schopné načítání plných textů článků. CSV datový soubor sice disponuje sloupcem plný text, ale tento je prázdný a služba není schopna plný text vracet. V CSV souboru je ale sloupec `Detail zprávy v NewtonOne` obsahující odkaz na plný text článku. Ten ve finále využijeme pro načítání.

V této fázi máme menší cíl - dokončení refaktorizace `newton_one.py`, které obsahuje datovou strukturu pro CSV, v promenné sloupce. Ty budeme potřebovat refaktorovat tak aby byly využitelné jednak v newton_one.py a jednak v nové utilitě. Možná by bylo dobré také podobným způsobem standardizovat výstupní formát?