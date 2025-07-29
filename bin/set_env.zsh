#!/bin/zsh

# nastavení Python prostředí pro funkci kódu pana mutiny
python3 -m venv ../.env # nastavit nové prostředí .env v rootu projektu
source ../.env/bin/activate # aktivovat toto prostředí
python3 -m pip install -r requirements.txt # instalovat závislosti shromážděné v souboru requirements.txt
