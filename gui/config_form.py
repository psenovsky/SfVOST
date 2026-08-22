import configparser
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGroupBox, QFormLayout, QMessageBox, QScrollArea
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.ini")

class ConfigForm(QWidget):
    def __init__(self):
        super().__init__()
        self.config = configparser.RawConfigParser()
        self.config.read(CONFIG_PATH, encoding="utf-8")
        self.fields = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        sections = {
            "database": "Databáze",
            "casove_limity": "Časové limity",
            "BlueSky": "BlueSky",
            "LLM": "LLM",
            "ner": "NER (pojmenované entity)",
            "scraper": "Scraper",
        }

        labels = {
            "database": {
                "host": "Hostitel",
                "port": "Port",
                "user": "Uživatel",
                "password": "Heslo",
                "dbname": "Název databáze",
                "charset": "Znaková sada",
            },
            "casove_limity": {
                "historie_dni": "Historie (dny)",
                "zpozdeni_mezi_dotazy": "Zpoždění mezi dotazy (s)",
            },
            "BlueSky": {
                "prah_jistoty": "Práh jistoty",
                "user": "Uživatel",
                "password": "Heslo",
            },
            "LLM": {
                "model": "Model",
                "max_tokens": "Max tokenů",
                "temperature": "Teplota",
                "host": "Hostitel",
                "port": "Port",
                "batch_size": "Velikost dávky",
            },
            "ner": {
                "modely": "Modely (JSON: jazyk → spaCy model)",
            },
            "scraper": {
                "delay": "Prodleva mezi články (s)",
            },
        }

        for section, title in sections.items():
            group = QGroupBox(title)
            form = QFormLayout()

            for key, label in labels[section].items():
                value = self.config.get(section, key, fallback="")
                line_edit = QLineEdit(value)
                if "password" in key:
                    line_edit.setEchoMode(QLineEdit.EchoMode.Password)
                self.fields[(section, key)] = line_edit
                form.addRow(label, line_edit)

            group.setLayout(form)
            scroll_layout.addWidget(group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Uložit")
        save_btn.clicked.connect(self.save_config)
        reset_btn = QPushButton("Resetovat")
        reset_btn.clicked.connect(self.reset_config)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(reset_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def save_config(self):
        for (section, key), widget in self.fields.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            self.config.set(section, key, widget.text())

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            self.config.write(f)

        QMessageBox.information(self, "Úspěch", "Nastavení bylo uloženo do config.ini")

    def reset_config(self):
        self.config.read(CONFIG_PATH, encoding="utf-8")
        for (section, key), widget in self.fields.items():
            widget.setText(self.config.get(section, key, fallback=""))
