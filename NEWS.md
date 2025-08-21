### v0.6

Tato verze se zcela zaměřuje na doplnění alespoň základního rozhraní pro ovládání analytických činností pomocí GUI.

### v0.5

- drobné úpravy v analýze sentimentu, přidání funkce pro vyčištění textu s cílem zvýšit výkon používaných modelů
- SocNetworks.py
  - odebrány některé neoužívané procedury
  - lepší kontrola data od - do
- refaktorovány skripty s cílem osamostatnit programovou logiku do samostatných tříd pro pozdější implementaci GUI

### v0.4

- první verze na GitHubu
- doplněny některé infformace o licenci

## v0.3

- skripty nyní reportují verzi balíku
- opravena chyba ve vyhodnocování jazyků v sentiment.py a ner.py - skript fungoval správně ve smyslu zpracování příspěvků, ale za určitých okolností generoval matoucí chybová hlášení navíc, která u uživatele mohla způsobit dojem, že skript nefunguje vůbec
- pro sentiment a NER implementovány abstraktní třídy modelů pro vynucení kompatibility v implementaci modelů způsobit dojem, že skript nefunguje vůbec

## v0.2

implementace nového pojetí celého balíku:

- zpracování je realizováno samostatnými skripty
- pro sentiment a NER jsou přidány modely přímo podporující češtinu
- analytika je implemtována v R Markdown

## v0.1

původní implementace Petra Mutiny z diplomové práce
