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

For further stage of development we will focus on preparation of data for further analysis. We will be developing new CLI utility in Python, which will take path to CSV file as a parameter. The CSV contain media monitoring using NewtonOne service for information (news, posts on social networks, etc) on certain emergency. The whole CSV will contain media only for one emergency, but through the whole event (from begining to recovery phase of the event).

We will need to gather relevant information for wither analysis, then amplify it, and finaly export the resulting dataset into one or more files.

The utility will be called `newton_one.py`.

The development will be realized in the phases. We will work on single phase at a time and test/update untile happy with results pf the phase. The fases are as follows:

- [x] Phase 1: Plan creation
- [x] Phase 2: CSV ingestion and preprocessing
- [ ] Phase 3: Analysis pipeline integration  - small models
- [ ] Phase 4: Optimization of API calls
- [ ] Phase 5: Analysis pipeline integration - LLM
- [ ] Phase 6: Keywords extraction
- [ ] Phase 7: Output consolidation and export
- [ ] Phase 8: Update documentation
- [ ] Phase 9: Review of Efficiency of BlueSky part of the project


### Phase 1: Plan creation

In this phase we will review an possibly adjust this plan. Example of CSV file is in `data/Tornádo 2021_čisté.csv`. 

As analytically relevant seem to be columns:
- Kód článku
- Datum publikování
- Název
- Zdroj    
- Země
- Typ média
- Anotace
- Plné znění
- Typ zprávy
- Sentiment
- Dosah

Column names are in czech and so is the content, at least dor this file. State identification, and thus possible language used could be `Země` column.

We will be performing:
- NER from column `Plné znění`
- sentiment analysis from columns `Plné znění` - must not not to overwrite `Sentiment` already in the file - name `SentimentLLM`
- disinformation detection from column `Plné znění`

These tasks to certain degree are already implemented in the project, we may be utilizing it wheever possible and if not possible, explore how to efficiently change the present code to allow such usage.

Changes in existing code must not impact provided functions by the project. By than I mean changes which would allow new analysis while disabling functions of BlueSky social network analysis.

There will also be new functionality, namely keywords detection based on columns `Anotace` and `Plné znění`. Separate keywords list is expected for both columns. In the future, we may want to analyze them. The analysis of possible differences between the keywords will be not part of the utility we are building.

### Phase 2: CSV ingestion and preprocessing

Build `newton_one.py` — a CLI utility that reads a NewtonOne CSV file and converts it into JSONL format suitable for downstream analysis tools.

#### Tasks:
- Accept path to a semicolon-delimited CSV file as the first positional argument (or via `-c`/`--csv`)
- we are presumming that the encoding of the file is in UTF-8
- Parse all 63 columns of `data/Tornado_2021_ciste.csv`, selecting the analytically relevant subset: Kód článku, Datum publikování, Název, Zdroj, Země, Typ média, Anotace, Plné znění, Typ zprávy, Sentiment, Dosah
- For each row, produce a JSON object with keys matching column names (Czech) and their values as strings — except where natural (Kód článku → str, Datum publikování → str in YYYY-MM-DD format if possible)
- Output to JSONL file specified via `-o`/`--output` argument
- ulitity should check whether the file exists and if yes as, whether the file should be overwtitten
- Print summary statistics: number of rows read, write progress bar

#### Design notes:
- Do NOT modify `data/Tornado_2021_ciste.csv` — it is reference data
- Handle quoting issues in semicolon-delimited CSV (fields may contain commas or quotes)
- Output JSONL must be line-buffered and deterministic (sorted keys for reproducibility)

### Phase 3: Analysis pipeline integration - small models

Wire together existing NER, sentiment (Czert-B + LLM-based), and disinformation detection into the new utility. Add `Sentiment_SM` as a parallel output alongside the pre-existing `Sentiment`. Ensure BlueSky functionality remains isolated in `src/BlueSky.py` — no changes to it.

In this phase we will be using small model implementations available in existing codebase.

#### Tasks:
- Reuse existing spaCy NER implementation (`src/ner_spacy.py`, language model mapping from `config.ini [ner]`) for `Plné znění` column in new field `NER_SM`
- Run Czert-B sentiment analysis (`src/sentiment_Czert_B.py`) on `Plné znění` and store results in new field `Sentiment_SM` (do NOT overwrite existing `Sentiment` column)
- Integrate zero-shot disinformation detection (`facebook/bart-large-mnli`) from `dezinformace.py` into the pipeline as a separate output field (e.g. `Dezinformace`) — include label and confidence score
- Process all rows in batches to avoid memory issues; respect existing timeout/configuration limits
- Preserve original data integrity: if any analysis step fails on a row, mark it with error indicator but continue processing

#### Design notes:
- Changes must NOT impact existing functions of `src/BlueSky.py` — BlueSky is disabled/isolated for this utility
- if `Plné znění` column is empry, perform analysis on `Anotace` column
- Do not modify `config.ini` — reuse it as-is; add new sections only if needed (e.g. `[newton_one]`)

### Phase 4: Optimization of API calls

`newton_one.py` and the modells it calls, hit very easily rate limits of HugingFace and we are the reason of it as we use the API extremely inefficiently. We need to ensure, that each API is initialized only once (best case scenario).

It should be possible for data, we are going to analyze, as they are czech only. This is not the case for BlueSky analysis portion of the project. I doubt that the solution for BlueSky will be so straign forward. Maybe create new file in `src` based on `src/sentiment_Czert_B.py` to not break BlueSky functionality. We will solve this problem in some future (yet unplanned) phases of the project. 

To further limit the problem we will focus on only one of the analyses NER, sentiment or disinformation - choose first one you encounter and comment others out in `newton_one.py`.

Focus on efficiency problems, caching, and repeted initializations of the models.

### Phase 5: Analysis pipeline integration - LLM

We will continue our work from phase 3. We will be using LLM for it now. Look into `data/llm.py` for implementation detail.

#### Tasks
- Implement  LLM-based sentiment analysis and NER using `config.ini [LLM]` settings; if endpoint is unavailable, skip gracefully with warning


#### Design notes
- since the media articles, posts, etc can be long it makes no sense to use batch processing
- make sure that signature of the functions in `data/llm.py` does not change - we need it for other utitilities in the project.
- the prompt in the  `data/llm.py` cannot change - derive new one from it for NER and sentiment analysis
- the resulting information should be inserted into new fields `sentiment_LLM` and `NER_LLM`

### Phase 6: Keywords extraction

Implement keyword detection from both `Anotace` and `Plné znění` columns using separate, configurable keyword lists. No cross-column analysis yet.

#### Tasks:
- use LLM for identification of the keywords
- Store results as JSON arrays of matched keyword strings per row
- Add fields `Klíčová_slova_Anotace` and `Klíčová_slova_Plné_znění` to the output JSON

#### Design notes:
- `Anotace` and `Plné znění` must be analyzed separately - each will produce its own list of keywords
- Empty/missing text values should produce empty arrays, not errors
- broaden implementation of the Analysis pipeline integration - LLM from phase 4

### Phase 7: Output consolidation and export

Combine all analysis results into a single output format (JSONL or CSV) per article, preserving the original column structure plus new derived fields.

#### Tasks:
- After running Phases 2–6 pipeline sequentially on each row, produce final consolidated JSONL with all fields merged
- Include: original columns + NER results + SentimentLLM + Dezinformace + keywords from both columns
- Add optional CSV export mode (`--format csv`) that writes back to semicolon-delimited format preserving column order
- Support parallel processing for large datasets (optional `--parallel` flag)
- Generate summary report printed to stdout: total rows, error counts per step, time elapsed

#### Design notes:
- Final output must be a single file containing all analyses — no intermediate files required unless using batch mode
- Output JSON keys should remain in Czech to match project convention

### Phase 8: Update documentation

Update `README.md` with newly added functionality from previous phases. 

### Phase 9: Review of Efficiency of BlueSky part of the project

Similarly to efficiency check from phase 4, we are going to look into BlueSky part of the project. Potentially we are working with hundreds or even thousands of the BlueSky's posts, which may lead to lot of calling to the models. We need to analyze existing code in order to identify possible improvements.

It is important that model caching is used as much as possible - look for repeated initializations of the models. For various languages different models will probably be needed. So we can't limit ourselves to single model.

What we can do is to manipulate with these models smartly for example by sorting loaded JSON objects using language which would allow us to limit number of initializations to number of languages in JSON multiplied by number of analyses we are performing (NER, sentiment analysis and disinformation detection)