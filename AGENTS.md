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
- [ ] Fáze 3: Vývoj a ladění webscraper
- [x] Fáze 3.1: doplnění prodlevy v načítání článků
- [x] Fáze 3.2: identifikace paywall
- [x] Fáze 3.3: Aktualizace GUI
- [x] Fáze 3.4: Detence potřebnosti použití scraperu
- [x] Fáze 3.5: Kódování jazyka
- [ ] Fáze 3.6: zdroj idnes.cz


### Fáze 1: Reorganizace `newton_one.py`

Dosud jsme analýzu řešili jedním skriptem, ukážalo se ale, že celý proces bude složitější a nemá proto smysl abychom kód drželi v jednom souboru. Vytvoř proto složku `newton_one` v složce `src` a to ní budeme refaktorovat stávající kód z `newton_one.py`. V root projektu by měl zůstat runner skript. Parametry příkazové řádky tohoto skriptu by prozatím tůstaly stejné.

Analyzuj obsah `newton_one.py`. Navrhni jak reorganizovat tento soubor a plán si nech schválit.

### Fáze 2: Příprava pro webscrapper

Naším celovým cílem, ke kterému dojdeme v dalších etapách vývoje, je návrh utility schopné načítání plných textů článků. CSV datový soubor sice disponuje sloupcem plný text, ale tento je prázdný a služba není schopna plný text vracet. V CSV souboru je ale sloupec `Detail zprávy v NewtonOne` obsahující odkaz na plný text článku. Ten ve finále využijeme pro načítání.

V této fázi máme menší cíl - dokončení refaktorizace `newton_one.py`, které obsahuje datovou strukturu pro CSV, v promenné sloupce. Ty budeme potřebovat refaktorovat tak aby byly využitelné jednak v newton_one.py a jednak v nové utilitě. Možná by bylo dobré také podobným způsobem standardizovat výstupní formát?

### Fáze 3: Vývoj a ladění webscraper

V této fázi budeme revidovat výsledek přípravné fáze. Jedná se o soubor `scraper.py` v rootu projektu a a obsah složky `src/*` kde je hlavní část scraperu.

Reviduj stav implementace a navrhni a implementuj chybějící části systému. Měli bychom se dostat do cílového stavu kdy na základě URL načtené z CSV souboru (pro experimenty máme připravené `data/Tornádo 2021_small.csv`) načteme obsah článku a ten vložíme do patříčného sloupce (`Plné znění`).

### Fáze 3.1: doplnění prodlevy v načítání článků

Pracujeme na @scraper.py . Potřeboval bych zajistit, že zbytečně nepřetížíme servery. Mezi pokusy o načtení proto vložíme krátkou prodlevu. Tato prodleva by měla být konfigurovatelná pomocí `config.ini`. Pro realizaci budeme proto potřebovat do tohoto souboru přidat další konfigurační direktivu nastavenou na 5. Bude se jednat o hodnotu v sekundách. Bude potřeba také upravit kód, který konfigurační soubor načítá.


### Fáze 3.2: identifikace paywall

V rámci načítání plných textů článků v rámci `scraper.py` potřebujeme identifikovat, že se nenačítá plná verze článku ale jeho zkrácená verze. Pro tyto účely do výstupního formátu doplníme položku `paywall` s možnými hodnotami `ano` nebo `ne`. Lze předpokládat, že každý zdroj toto bude řešit odlišně a tím pádem to budeme muset zohlednit v kódu projektu.

Pro Zdroj `zpravy.iDNES.cz` je informace o paywallu dostupná v metainformacích stránky, konkrétně:

`<meta name="cXenseParse:qiw-content" content="premium">`

Začal jsi implementovat řešení v `src/detect_paywall`. Podívej se kde jsi skončil a zkus pokračovat.

### Fáze 3.3: Aktualizace GUI

`config.ini` se změnil. Přidali jsme tam položku delay, která je zapracovaná do kódu projektu, kromě GUI aplikace v `gui/config_form.py` aktualizuj formulář, přidej podporu pro delay. Nezapomeň upravit nejen formulář, načítání, ale také ukládání konfigurace.

### Fáze 3.4: Detence potřebnosti použití scraperu

Načítání plné verze článku ppomocí `scraper.py` by mělo proběhnout pouze v případě, že plný text v základním souboru CSV není vyplněn. Zkontroluj, že se zbytečně nesnažíme scrapovat web i v případě, kdy to není nutné.

### Fáze 3.5: Kódování jazyka

Zdá se mi, že logika scaperu (`scraper.py`) je příliš složitá. Zkusíme proto postupně diagnostikovat, zda se postupuje při zpracování správným způsobem. 

Postup:
1) načte se stránka - tak, jak je, tedy bez transformací
2) detekuje se kodování
    - primární zdroj informací o kódování je `<meta charset="kódování">`
    - teprve pokud není meta informace o kódování dostupná, provede se detekce jinak
3) pokud detekované kódování není `utf-8` je nutné provést konverzi.

Pokud jsem stránku načetl do proměnné `data`, pak lze použít transformaci:

```Python
text = data.decode("cp1250")
utf8_data = text.encode("utf-8") 
```

Místo cp1250 se doplní detekované kódování. Našim cílovým kódováním je `utf-8`. Pokud v tomto kódování stránka již je neprovádíme další transformace.

Ověř, že tato logika platí.

### Fáze 3.6: zdroj idnes.cz

V rámci naší implementace `scraper.py` zdroj *.idnes.cz má problém - nenečítá se totiž pro něj vše, co má. Tento zdroj je divný, protože obsah má rozdělený do dvou částí. První obsahuje první odstavec. CMS ji označuje jako popis a je přítomen v: `<div class="opener" itemprop="description">`. Druhá `<div itemprop="articleBody">` obsahuje samotný obsah článku.

Do plného textu potřebujeme obě části. 

V současnosti detekujeme pouze první (description) část. Druhá zůstává nedetekovaná.

Uvažuji, jak nejlépe tento problém vyřešit. Různé zdroje mohou prezentovat data různým způsobem. V současné době uvažujeme několik obecných, na zdroji nezávislých, strategiích popisujících to, kde hledat obsah. Mám obavu, že toto nebude stačit a budeme muset implementovat některé strategie, které jsou závislé na zdroji.

Těďka budeme implementovat strategii pro získání plného textu pro domény: `zpravy.iDNES.cz`, `www.zpravy.iDNES.cz` a `www.idnes.cz`. 

Navrhuji načíst vše mezi tagy: 
-  `<div class="opener" itemprop="description">` a jemu přináležející `</div>`
-  `<div itemprop="articleBody">` a jemu přináležející `</div>`

Článek z iDnes, o který se mimo jiné jedná je na: `https://www.idnes.cz/zpravy/domaci/tornado-hodoninsko-chmu-pocasi-boure.A210624_224841_domaci_vlc`.

#### pokus o úpravu (evoluci generovaného kód)

Webscraping implementace ve `scraper.py` pro domény `zpravy.iDNES.cz`, `www.zpravy.iDNES.cz` a `www.idnes.cz` se úplně nepovedla. Místo obsahu v `<div class="opener" itemprop="description">` a `<div itemprop="articleBody">`. Se vybral description z meta hlavičky a text pro paywall. Tedy nenačetla se žádná z požadovaných částí.

Pro článek `https://www.idnes.cz/zpravy/domaci/tornado-hodoninsko-chmu-pocasi-boure.A210624_224841_domaci_vlc` je obsah předmětných tagů následující

```html
<div class="opener" itemprop="description">
                        Tornádo, které zpustošilo sedm obcí na Hodonínsku, se mohlo prohnat prakticky kdekoli v Česku. Oblast není ničím specifická. „Vždy záleží na síle a typu bouře, ve které se jev objeví,“ říká ke čtvrtečním událostem meteoroložka Jitka Kučerová z brněnské pobočky Českého hydrometeorologického ústavu. To nejhorší už se podle ní přehnalo a bouřková činnost bude do rána po republice zvolna slábnout.
                    </div>
```

```html
<div itemprop="articleBody"><p><b>Nasvědčovalo něco tomu, že přijde tornádo?</b><br>Ne. Je určitá pravděpodobnost, že se při některých situacích může takovýto jev objevit, jenže jde jen o předpověď. My jako meteorologové nepředpovídáme, jestli bude tornádo nebo ne. Takto specifickými předpověďmi se zabývá například <a class="text-link" target="_blank" href="https://www.estofex.org/">ESTOFEX</a>, European Storm Forecast Experiment (<i>volně přeloženo jako Evropské experimentální předpovědi bouří, jedná se o volnočasový projekt evropských meteorologů a studentů meteorologie, pozn. red.</i>). Jsou to takoví nadšenci, kteří se zabývají předpověďmi bouřek a píší, jestli čekají to nebo ono. Ti naznačovali, že k něčemu takovému může potenciálně dojít. </p><!--ad--></div>
```

Výsledný text by měl být podobný 


    Tornádo, které zpustošilo sedm obcí na Hodonínsku, se mohlo prohnat prakticky kdekoli v Česku. Oblast není ničím specifická. „Vždy záleží na síle a typu bouře, ve které se jev objeví,“ říká ke čtvrtečním událostem meteoroložka Jitka Kučerová z brněnské pobočky Českého hydrometeorologického ústavu. To nejhorší už se podle ní přehnalo a bouřková činnost bude do rána po republice zvolna slábnout.

    Nasvědčovalo něco tomu, že přijde tornádo?
    Ne. Je určitá pravděpodobnost, že se při některých situacích může takovýto jev objevit, jenže jde jen o předpověď. My jako meteorologové nepředpovídáme, jestli bude tornádo nebo ne. Takto specifickými předpověďmi se zabývá například ESTOFEX, European Storm Forecast Experiment (volně přeloženo jako Evropské experimentální předpovědi bouří, jedná se o volnočasový projekt evropských meteorologů a studentů meteorologie, pozn. red.). Jsou to takoví nadšenci, kteří se zabývají předpověďmi bouřek a píší, jestli čekají to nebo ono. Ti naznačovali, že k něčemu takovému může potenciálně dojít. 
    
#### Ověření spouštění kódu idnes

Pracujeme na `scraper.py`. Momentálně řešíme specifika různých poskytovatelů obsahu. Naposledy jsme pracovali na poskytovateli idnes.cz, kde obsah článku byl  v `<div class="opener" itemprop="description">` a `<div itemprop="articleBody">`. Text se ale načítá chybně. Existuje několik možností proč tomu tak je. Potřebuji, aby jsme je začali vylučovat. Proto prosím ověř, že část určená pro vyhodnocování tohoto poskytovatele se skutečně pouští.

Problémový je první zaznam v `data/Tornádo 2021_small.csv`.