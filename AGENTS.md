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

- [ ] Phase 1: Plan creation


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

Create further stages of the plan.
