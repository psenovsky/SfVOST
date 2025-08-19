from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QCheckBox, QFileDialog, QDateEdit, QRadioButton, QButtonGroup,
    QMessageBox
)
from src.BlueSky import BlueSky
from src.ner import ner
from src.sentiment import sentiment

import sys
import json

class DataForm(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Formulář pro analýzu dat")
        self.init_ui()

    def init_ui(self):
        """
        inicializace UI (vytvoření formuláře a nastavení jeho prvků)
        """
        layout = QVBoxLayout()

        # Výběr zdroje dat
        layout.addWidget(QLabel("Jak postupovat"))
        self.radio_bluesky = QRadioButton("Načíst ze sítě BlueSky")
        self.radio_json = QRadioButton("Načíst ze souboru JSONL")
        self.radio_bluesky.setChecked(True)
        self.source_group = QButtonGroup()
        self.source_group.addButton(self.radio_bluesky)
        self.source_group.addButton(self.radio_json)
        layout.addWidget(self.radio_bluesky)
        layout.addWidget(self.radio_json)

        # Načtení ze sítě BlueSky
        layout.addWidget(QLabel("Načíst ze sítě BlueSky"))
        self.keywords_input = QLineEdit()
        self.keywords_input.setPlaceholderText("klíčová slova (oddělená čárkou)")
        layout.addWidget(self.keywords_input)

        date_layout = QHBoxLayout()
        self.date_from = QDateEdit()
        self.date_to = QDateEdit()
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(QLabel("od:"))
        date_layout.addWidget(self.date_from)
        date_layout.addWidget(QLabel("do:"))
        date_layout.addWidget(self.date_to)
        layout.addLayout(date_layout)

        # Načtení ze souboru JSONL
        layout.addWidget(QLabel("Načtení ze souboru (JSONL)"))
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_button = QPushButton("...")
        self.file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(self.file_button)
        layout.addLayout(file_layout)

        # Analýzy
        layout.addWidget(QLabel("Realizovat analýzy"))
        self.ner_checkbox = QCheckBox("pojmenované entity (NER)")
        self.sentiment_checkbox = QCheckBox("sentiment")
        layout.addWidget(self.ner_checkbox)
        layout.addWidget(self.sentiment_checkbox)

        # Uložení výsledků
        layout.addWidget(QLabel("Uložit výsledky analýzy do souboru (JSONL)"))
        save_layout = QHBoxLayout()
        self.save_input = QLineEdit()
        save_button = QPushButton("...")
        save_button.clicked.connect(self.select_save_file)
        save_layout.addWidget(self.save_input)
        save_layout.addWidget(save_button)
        layout.addLayout(save_layout)

        # analyzovat
        analyze_button = QPushButton("Analyzovat")
        analyze_button.clicked.connect(self.analyzovat)
        layout.addWidget(analyze_button)

        # Reakce na změnu výběru zdroje
        self.radio_bluesky.toggled.connect(self.toggle_sections)
        self.toggle_sections()

        self.setLayout(layout)

    def toggle_sections(self):
        """
        událost změna výběru zdroje dat - povolí relevantní prvky GUI a zakáže irelevantní
        """
        if self.radio_bluesky.isChecked():
            self.keywords_input.setEnabled(True)
            self.date_from.setEnabled(True)
            self.date_to.setEnabled(True)
            self.file_input.setEnabled(False)
            self.file_button.setEnabled(False)
        elif self.radio_json.isChecked():
            self.keywords_input.setEnabled(False)
            self.date_from.setEnabled(False)
            self.date_to.setEnabled(False)
            self.file_input.setEnabled(True)
            self.file_button.setEnabled(True)

    def select_file(self):
        """
        událost po na tlačítko "..." v poli pro nastavení cesty k souboru ze kterého se budou načítat příspěvky k analýze
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Vyber soubor", "", "JSON soubor(*.json);;JSONL Files (*.jsonl)")
        if file_path:
            self.file_input.setText(file_path)

    def select_save_file(self):
        """
        událost po na tlačítko "..." v poli pro nastavení cesty k souboru pro uložení výsledků
        """
        file_path, _ = QFileDialog.getSaveFileName(self, "Ulož soubor", "", "JSON soubor(*.json);;JSONL Files (*.jsonl)")
        if file_path:
            self.save_input.setText(file_path)

    def analyzovat(self):
        """
        událost po kliknutí na tlačítko Analyzovat
        """
        # kontrola vyplnění parametrů
        error = ""
        prispevky = ""
        nr = None
        sen = None
        if not self.ner_checkbox.isChecked() and not self.sentiment_checkbox.isChecked():
            error += "- Vyberte alespoň jednu metod analýzy\n"
        if self.save_input.text() == "":
            error += "- není jasné kam s výsledky analýzy\n"
        if self.radio_bluesky.isChecked():
            # implementovat kontrolu parametrů pro BlueSky
            if self.keywords_input.text() == "":
                error += "- Zadejte klíčová slova\n"
            if self.date_from.date() == "":
                error += "- Zadejte data od\n"
            if self.date_to.date() == "":
                error += "- Zadejte data do\n"
            if error != "":
                QMessageBox.warning(self, "Chyba", error)
                return
            bs = BlueSky(postJSONL = "", keywords = self.keywords_input.text(), since = self.date_from.date(), until = self.date_to.date())
            prispevky = bs.prispevky
            if self.ner_checkbox.isChecked():
                nr = ner(postsPath = "", nerJSONL = "", postsJSONL = prispevky)
                prispevky = nr.ner
            if self.sentiment_checkbox.isChecked():
                sen = sentiment(cestaJSON = "", cestaExport = "", postsJSONL = prispevky)
                prispevky = sen.sentiment
        elif self.radio_json.isChecked():
            if self.file_input.text() == "":
                error += "Zadejte soubor ze kterého se budou načítat příspěvky k analýze\n"
            if error != "":
                QMessageBox.warning(self, "Chyba", error)
                return
            if self.ner_checkbox.isChecked():
                nr = ner(postsPath = self.file_input.text(), nerJSONL = "", postsJSONL = "")
                prispevky = nr.ner
            if self.sentiment_checkbox.isChecked() and prispevky == "":
                sen = sentiment(cestaJSON = self.file_input.text(), cestaExport = "", postsJSONL = "")
                prispevky = sen.sentiment
            elif self.sentiment_checkbox.isChecked() and prispevky != "":
                sen = sentiment(cestaJSON = "", cestaExport = "", postsJSONL = prispevky)
                prispevky = sen.sentiment

        with open(self.save_input.text(), "w", encoding="utf-8") as f:
            for post in prispevky:
                f.write(json.dumps(post))
                f.write("\n")
        print(f"✅ ... uloženo do souboru {self.save_input.text()}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = DataForm()
    form.show()
    sys.exit(app.exec())
