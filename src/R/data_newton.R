# Třída DataNewton
#
# Načte výstup analýzy Newton One ve formátu JSON Lines (jeden JSON objekt na
# řádek, např. data/torando_spojene_Gemma4-12b.jsonl) a připraví z něj čtyři
# tabulky:
#
#   zpravy        – zprávy s jednotnými typy (datum, paywall, dosah, sentiment)
#   ner           – dlouhý formát entit: jeden řádek = jedna entita jednoho článku
#   klicova_slova – dlouhý formát klíčových slov
#   zdroje        – číselník zdrojů (ID, zdroj)
#
# Postup převodu v konstruktoru odpovídá ručnímu zpracování v souboru
# data/newton_one.Rmd; jednotlivé kroky jsou oddělené do privátních metod.
# Zdrojová data se přitom nijak nemění, všechny úpravy vznikají až v paměti.
#
# Použití:
#
#   data <- DataNewton$new("data/torando_spojene_Gemma4-12b.jsonl")
#   data$prehled()
#   data$ulozit_zdroje("zdroje.csv")
#   head(data$ner)

DataNewton <- R6::R6Class(
  classname = "DataNewton",

  public = list(
    #' @description Cesta k JSONL souboru, ze kterého byla data načtena.
    cesta = NULL,

    #' @description Zprávy s jednotnými typy hodnot.
    zpravy = NULL,

    #' @description Entity nalezené modelem v dlouhém formátu (ID, typ, entita).
    ner = NULL,

    #' @description Klíčová slova nalezená modelem v dlouhém formátu
    #'   (ID, klicove_slovo, klicove_slovo_norm).
    klicova_slova = NULL,

    #' @description Číselník zdrojů (ID, zdroj).
    zdroje = NULL,

    #' @description
    #' Načte JSONL soubor a provede všechny kroky převodu.
    #'
    #' @param cesta Cesta k JSONL souboru s výstupem analýzy.
    initialize = function(cesta) {
      if (!is.character(cesta) || length(cesta) != 1L) {
        stop("Cesta k JSONL souboru musí být jediný řetězec.", call. = FALSE)
      }
      if (!file.exists(cesta)) {
        stop(sprintf("Vstupní soubor neexistuje: %s", cesta), call. = FALSE)
      }
      self$cesta <- cesta

      zpravy <- private$importovat(cesta)
      private$overit_sloupce(zpravy)

      # jednotlivé části převodu – každá jako samostatná privátní metoda
      zpravy <- private$sjednotit_datum(zpravy)
      zpravy <- private$sjednotit_paywall(zpravy)
      zpravy <- private$sjednotit_dosah(zpravy)
      zpravy <- private$nahradit_prazdne(zpravy)
      zpravy <- private$sjednotit_sentiment(zpravy)
      zpravy <- private$sjednotit_dezinformace(zpravy)

      self$zpravy <- zpravy
      self$ner <- private$prevest_ner(zpravy)
      self$klicova_slova <- private$prevest_klicova_slova(zpravy)
      self$zdroje <- private$sestavit_zdroje(zpravy)

      invisible(self)
    },

    #' @description
    #' Vypíše přehled dat: počty záznamů, prázdné hodnoty, rozložení sentimentu
    #' a dezinformací, kontrolu NER a klíčových slov i články bez nalezených
    #' entit. Odpovídá kontrolním blokům v data/newton_one.Rmd.
    #'
    #' @return Třída (nevratná hodnota).
    prehled = function() {
      zpravy <- self$zpravy

      cat("\n=== Zdroj dat ===\n")
      cat(sprintf("Soubor:  %s\n", self$cesta))
      cat(sprintf("Záznamů: %d\n", nrow(zpravy)))
      cat(sprintf("Sloupců: %d\n", ncol(zpravy)))
      if ("Manuálně" %in% names(zpravy)) {
        cat(sprintf("Ručně zanacených: %d\n",
                    sum(zpravy[["Manuálně"]] == "A", na.rm = TRUE)))
      }

      cat("\n=== Prázdné hodnoty (NA) ===\n")
      prazdne <- private$pocet_na(zpravy)
      prazdne <- prazdne[!is.na(prazdne) & prazdne > 0L]
      if (length(prazdne) == 0L) {
        cat("Žádné.\n")
      } else {
        print(sort(prazdne, decreasing = TRUE))
      }

      if ("Datum publikování" %in% names(zpravy)) {
        cat("\n=== Datum publikování ===\n")
        cat(paste(class(zpravy[["Datum publikování"]]), collapse = " / "), "\n")
        print(table(format(zpravy[["Datum publikování"]], "%Y-%m-%d"),
                     useNA = "ifany"))
      }

      if ("Paywall" %in% names(zpravy)) {
        cat("\n=== Paywall ===\n")
        print(table(zpravy[["Paywall"]], useNA = "ifany"))
      }

      if ("Dosah" %in% names(zpravy)) {
        cat("\n=== Dosah ===\n")
        print(summary(zpravy[["Dosah"]]))
      }

      cat("\n=== Sentiment ===\n")
      for (sloupec in c("Sentiment", "sentiment_LLM")) {
        if (sloupec %in% names(zpravy)) {
          cat(sprintf("– %s:\n", sloupec))
          print(table(zpravy[[sloupec]], useNA = "ifany"))
        }
      }
      if (all(c("Sentiment", "sentiment_LLM") %in% names(zpravy))) {
        cat("– porovnání obou modelů:\n")
        print(table(Sentiment = zpravy[["Sentiment"]],
                    sentiment_LLM = zpravy[["sentiment_LLM"]],
                    useNA = "ifany"))
      }

      if ("dezinformace_LLM" %in% names(zpravy)) {
        cat("\n=== Dezinformace ===\n")
        print(table(zpravy[["dezinformace_LLM"]], useNA = "ifany"))
      }

      cat("\n=== NER ===\n")
      cat(sprintf("Řádků: %d\n", nrow(self$ner)))
      cat(sprintf("Různých názvů entit: %d\n", length(unique(self$ner$entita))))
      cat(sprintf("Článků s entitou: %d z %d\n",
                  length(unique(self$ner$ID)), nrow(zpravy)))
      if (nrow(self$ner) > 0L) {
        print(dplyr::count(self$ner, typ, sort = TRUE))
      }
      bez <- self$bez_entit()
      cat(sprintf("Článků bez entity: %d\n", nrow(bez)))
      if (nrow(bez) > 0L) {
        print(utils::head(bez, 10))
      }

      cat("\n=== Klíčová slova ===\n")
      cat(sprintf("Výskytů: %d\n", nrow(self$klicova_slova)))
      cat(sprintf("Různých klíčových slov: %d\n",
                  length(unique(self$klicova_slova$klicove_slovo))))
      cat(sprintf("Článků s klíčovým slovem: %d z %d\n",
                  length(unique(self$klicova_slova$ID)), nrow(zpravy)))
      if (nrow(self$klicova_slova) > 0L) {
        cat("– nejčastější (včetně původního psaní):\n")
        print(utils::head(
          dplyr::count(self$klicova_slova, klicove_slovo, sort = TRUE), 15))
        cat("– nejčastější (bez rozlišování velikosti písmen):\n")
        print(utils::head(
          dplyr::count(self$klicova_slova, klicove_slovo_norm, sort = TRUE), 15))
      }

      cat("\n=== Zdroje ===\n")
      cat(sprintf("Různých zdrojů: %d\n", nrow(self$zdroje)))
      print(utils::head(self$zdroje, 10))

      invisible(self)
    },

    #' @description
    #' Uloží číselník zdrojů do CSV souboru (středníkový oddělovač, kódování
    #' UTF-8), stejně jako exportní blok v data/newton_one.Rmd.
    #'
    #' @param cesta Cesta k výstupnímu CSV souboru.
    #' @return Cesta k uloženému souboru (nevratná hodnota).
    ulozit_zdroje = function(cesta = "zdroje.csv") {
      utils::write.csv2(self$zdroje, file = cesta, row.names = FALSE)
      message(sprintf("✅ Zdroje uloženy do souboru %s (%d řádků)", cesta, nrow(self$zdroje)))
      invisible(cesta)
    },

    #' @description
    #' Vrátí články, u kterých model nenašel žádnou entitu.
    #'
    #' @return Tabulka se sloupci ID, Kód článku, Název a Zdroj.
    bez_entit = function() {
      sloupce <- intersect(c("ID", "Kód článku", "Název", "Zdroj"),
                           names(self$zpravy))
      dplyr::filter(self$zpravy[, sloupce, drop = FALSE],
                    !ID %in% self$ner$ID)
    },

    #' @description
    #' Vrátí entity obohacené o metadata článku (Název, Zdroj, Datum publikování).
    #' Sloupec ID slouží jako cizí klíč do tabulky zpravy.
    #'
    #' @return Tabulka entit s připojenými metadaty.
    s_metadaty = function() {
      metadata <- self$zpravy[, intersect(c("ID", "Název", "Zdroj",
                                           "Datum publikování"),
                                          names(self$zpravy)), drop = FALSE]
      dplyr::left_join(self$ner, metadata, by = "ID")
    },

    #' @description
    #' Stručný výpis: zdroj, počty záznamů, entit, klíčových slov a zdrojů.
    print = function(...) {
      cat(sprintf(
        "<DataNewton> %s: %d zpráv, %d entit, %d klíčových slov, %d zdrojů\n",
        basename(self$cesta), nrow(self$zpravy), nrow(self$ner),
        nrow(self$klicova_slova), nrow(self$zdroje)))
      invisible(self)
    }
  ),

  private = list(
    #' @description Typy entit, které se z NER_LLM převádějí do dlouhého formátu.
    typy_ner = c("DATE", "FAC", "GPE", "LOC", "ORG", "PER"),

    #' @description
    #' Načte JSONL soubor (formát JSON Lines – jeden JSON objekt na řádek)
    #' a přidá sloupec ID s pořadovým číslem záznamu.
    importovat = function(cesta) {
      spojeni <- file(cesta, open = "r", encoding = "UTF-8")
      on.exit(close(spojeni), add = TRUE)

      zpravy <- tibble::as_tibble(
        jsonlite::stream_in(spojeni, pagesize = 10000, verbose = FALSE)
      )
      zpravy$ID <- seq_len(nrow(zpravy))

      message(sprintf("✅ Načteno %d záznamů (%d sloupců) ze souboru %s",
                      nrow(zpravy), ncol(zpravy), cesta))
      zpravy
    },

    #' @description
    #' Ověří, zda data obsahují očekávané sloupce. Chybějící povinné sloupce
    #' jsou varování, chybějící sloupce LLM analýzy jen informace – převod
    #' se u nich přeskočí a výsledná tabulka bude prázdná.
    overit_sloupce = function(zpravy) {
      povinne <- c("Kód článku", "Název", "Zdroj", "Datum publikování")
      chybi <- setdiff(povinne, names(zpravy))
      if (length(chybi) > 0L) {
        warning(sprintf("V datech chybí sloupce: %s",
                        paste(chybi, collapse = ", ")), call. = FALSE)
      }

      volitelne <- c("Paywall", "Dosah", "Sentiment", "Manuálně",
                     "NER_LLM", "klíčová slova_LLM", "sentiment_LLM",
                     "dezinformace_LLM")
      chybi <- setdiff(volitelne, names(zpravy))
      if (length(chybi) > 0L) {
        message(sprintf("ℹ️ V datech chybí sloupce, jejichž převod se přeskočí: %s",
                        paste(chybi, collapse = ", ")))
      }

      invisible(NULL)
    },

    #' @description
    #' Datum publikování: ručně zanacené záznamy mají formát `25.6.2021`,
    #' automatické ISO formát `2021-06-25`. `parse_date_time` s nabídkou obou
    #' možností rozpozná oba formáty a převede je na skutečný typ `Date`.
    sjednotit_datum = function(zpravy) {
      if (!"Datum publikování" %in% names(zpravy)) {
        return(zpravy)
      }

      zpravy[["Datum publikování"]] <- as.Date(lubridate::parse_date_time(
        x = as.character(zpravy[["Datum publikování"]]),
        orders = c("Ymd", "dmy"),
        trunc = 2
      ))
      zpravy
    },

    #' @description
    #' Paywall: `jsonlite` načte sloupec jako text, protože část hodnot není
    #' logická. Sjednotíme na logický typ, přičemž prázdné hodnoty a `ne`
    #' znamenají `FALSE`.
    sjednotit_paywall = function(zpravy) {
      if (!"Paywall" %in% names(zpravy)) {
        return(zpravy)
      }

      p <- tolower(trimws(as.character(zpravy[["Paywall"]])))
      zpravy[["Paywall"]] <- dplyr::case_when(
        p %in% c("true", "ano", "1", "yes") ~ TRUE,
        p %in% c("false", "ne", "0", "no") ~ FALSE,
        TRUE                                 ~ NA
      )
      zpravy
    },

    #' @description
    #' Dosah: u ručně zanacených záznamů je místo čísla prázdný řetězec.
    #' Převedeme na číselný typ a prázdné hodnoty nahradíme `NA`.
    sjednotit_dosah = function(zpravy) {
      if (!"Dosah" %in% names(zpravy)) {
        return(zpravy)
      }

      hodnoty <- trimws(as.character(zpravy[["Dosah"]]))
      zpravy[["Dosah"]] <- suppressWarnings(
        as.numeric(ifelse(is.na(hodnoty) | hodnoty == "", NA_character_, hodnoty))
      )
      zpravy
    },

    #' @description
    #' Ručně zanacené záznamy mají v řadě sloupců prázdný řetězec místo
    #' skutečné hodnoty. Nahradíme je `NA`, aby se daly filtrovat a agregovat
    #' jednotně.
    nahradit_prazdne = function(zpravy) {
      dplyr::mutate(zpravy, dplyr::across(
        dplyr::where(is.character),
        ~ dplyr::na_if(trimws(.x), "")
      ))
    },

    #' @description
    #' Jednotné názvosloví sentimentu: v datech jsou dva paralelní sloupce
    #' (`Sentiment` a `sentiment_LLM`), každý používá jinou velikost písmen.
    #' Sjednotíme velikost písmen na malá a přejmenujeme na názvy bez diakritiky.
    sjednotit_sentiment = function(zpravy) {
      for (sloupec in c("Sentiment", "sentiment_LLM")) {
        if (!(sloupec %in% names(zpravy))) {
          next
        }
        hodnoty <- tolower(trimws(zpravy[[sloupec]]))
        zpravy[[sloupec]] <- dplyr::recode(hodnoty,
                                           "negativní" = "negativni",
                                           "pozitivní" = "pozitivni",
                                           "neutrální" = "neutralni")
      }
      zpravy
    },

    #' @description
    #' Sloupec `dezinformace_LLM` používá hodnoty `ano` / `ne`, u ručně
    #' zanacených záznamů je prázdný. Sjednotíme na hodnoty `ano` / `ne` / `NA`.
    sjednotit_dezinformace = function(zpravy) {
      if (!"dezinformace_LLM" %in% names(zpravy)) {
        return(zpravy)
      }

      zpravy[["dezinformace_LLM"]] <- tolower(trimws(zpravy[["dezinformace_LLM"]]))
      zpravy
    },

    #' @description
    #' Převod vnořeného `NER_LLM` (data.frame se sloupci pojmenovanými podle
    #' typů entit, každý se seznamem nalezených hodnot) do dlouhého formátu:
    #' jeden řádek = jedna entita jednoho článku, se sloupci ID, typ a entita.
    prevest_ner = function(zpravy) {
      typy <- private$typy_ner
      if (nrow(zpravy) == 0L) {
        return(tibble::tibble(ID = integer(), typ = character(),
                              entita = character()))
      }
      nested <- private$pripojit_ner(zpravy, typy)

      tibble::tibble(ID = zpravy$ID) |>
        dplyr::bind_cols(nested) |>
        tidyr::pivot_longer(cols = dplyr::all_of(typy),
                            names_to = "typ", values_to = "hodnoty") |>
        tidyr::unnest(hodnoty) |>
        dplyr::filter(!is.na(hodnoty), hodnoty != "") |>
        dplyr::rename(entita = hodnoty)
    },

    #' @description
    #' Vrátí `NER_LLM` jako tabulku se sloupci typů entit, která má přesně tolik
    #' řádků jako zprávy. Chybějící typy doplníme prázdnými hodnotami a chybějící
    #' řádky přidáme na konec, aby šly entity bezpečně přiřadit k článkům.
    pripojit_ner = function(zpravy, typy) {
      pocet <- nrow(zpravy)
      prazdna <- function(n) {
        # sloupec prázdných seznamů – I() zabrání, aby data.frame prázdný
        # seznam zahodil
        as.data.frame(
          stats::setNames(rep(list(I(rep(list(character(0)), n))), length(typy)),
                          typy),
          stringsAsFactors = FALSE
        )
      }

      if (!("NER_LLM" %in% names(zpravy)) || is.null(zpravy[["NER_LLM"]])) {
        message("⚠️ Sloupec NER_LLM v datech chybí – tabulka entit bude prázdná.")
        return(prazdna(pocet))
      }
      if (!is.data.frame(zpravy[["NER_LLM"]])) {
        message("⚠️ Sloupec NER_LLM nemá očekávanou strukturu – tabulka entit bude prázdná.")
        return(prazdna(pocet))
      }

      nested <- tibble::as_tibble(zpravy[["NER_LLM"]], .name_repair = "minimal")
      chybi <- pocet - nrow(nested)
      if (chybi > 0L) {
        message(sprintf(
          "⚠️ NER_LLM má %d řádků místo %d – %d chybějících řádků doplněno prázdnými hodnotami.",
          nrow(nested), pocet, chybi
        ))
        nested <- dplyr::bind_rows(nested, prazdna(chybi))
      }
      if (nrow(nested) > pocet) {
        stop(sprintf(
          "NER_LLM má %d řádků, ale načteno jen %d záznamů – data nedávají smysl.",
          nrow(nested), pocet
        ), call. = FALSE)
      }

      # typy, které v datech chybí, doplníme prázdnými hodnotami
      for (typ in setdiff(typy, names(nested))) {
        nested[[typ]] <- replicate(pocet, character(0), simplify = FALSE)
      }
      nested <- nested[, typy, drop = FALSE]

      # hodnoty sjednotíme na textové vektory, jinak by se je nepodařilo
      # rozbalit (prázdné pole JSON se načte jako prázdný seznam, ne jako
      # prázdný textový vektor)
      for (typ in typy) {
        nested[[typ]] <- private$textove_hodnoty(nested[[typ]])
      }
      nested
    },

    #' @description
    #' Převede sloupec se seznamy nalezených hodnot na seznam textových vektorů.
    #' `NULL`, prázdný seznam i prázdný text se sjednotí na `character(0)`,
    #' případné vnořené seznamy se rozbalí. Bez tohoto kroku nelze sloupec
    #' rozbalit přes `tidyr::unnest`.
    textove_hodnoty = function(hodnoty) {
      lapply(hodnoty, function(x) {
        if (is.null(x)) {
          return(character(0))
        }
        if (is.list(x)) {
          x <- unlist(x, use.names = FALSE)
        }
        if (length(x) == 0L) {
          return(character(0))
        }
        as.character(x)
      })
    },

    #' @description
    #' Sloupec `klíčová slova_LLM` je jen sloupec typu `list`, kde každý prvek
    #' obsahuje textový vektor nalezených klíčových slov. Stačí ho rozbalit na
    #' jednotlivé řádky – jeden řádek = jedno klíčové slovo jednoho článku.
    #' Velikost písmen u klíčových slov význam nese (model psal vlastní jména
    #' s velkým písmenem), proto ponecháváme původní psaní a vedle něj doplňujeme
    #' normalizovaný sloupec pro agregaci bez rozlišování velikosti písmen.
    prevest_klicova_slova = function(zpravy) {
      if (nrow(zpravy) == 0L) {
        return(tibble::tibble(ID = integer(), klicove_slovo = character(),
                              klicove_slovo_norm = character()))
      }
      if (!("klíčová slova_LLM" %in% names(zpravy))) {
        message("⚠️ Sloupec klíčová slova_LLM v datech chybí – tabulka klíčových slov bude prázdná.")
        zpravy[["klíčová slova_LLM"]] <- vector("list", nrow(zpravy))
      }
      zpravy[["klíčová slova_LLM"]] <- private$textove_hodnoty(
        zpravy[["klíčová slova_LLM"]]
      )

      zpravy |>
        dplyr::select(ID, `klíčová slova_LLM`) |>
        tidyr::unnest(`klíčová slova_LLM`, keep_empty = FALSE) |>
        dplyr::rename(klicove_slovo = `klíčová slova_LLM`) |>
        dplyr::filter(!is.na(klicove_slovo), klicove_slovo != "") |>
        dplyr::mutate(klicove_slovo_norm = tolower(klicove_slovo))
    },

    #' @description
    #' Číselník zdrojů – unikátní názvy zdrojů seřazené abecedně s číslem
    #' podle pořadí.
    sestavit_zdroje = function(zpravy) {
      if (!("Zdroj" %in% names(zpravy))) {
        return(tibble::tibble(ID = integer(), zdroj = character()))
      }

      zdroj <- unique(as.character(zpravy[["Zdroj"]]))
      zdroj <- sort(zdroj[!is.na(zdroj)])
      tibble::tibble(ID = seq_along(zdroj), zdroj = zdroj)
    },

    #' @description
    #' Počet chybějících hodnot (`NA`) v jednotlivých sloupcích. Sloupce s
    #' vnořenými hodnotami (`NER_LLM`, `klíčová slova_LLM`) se nepočítají.
    pocet_na = function(zpravy) {
      vapply(zpravy, function(sloupec) {
        if (is.atomic(sloupec)) sum(is.na(sloupec)) else NA_integer_
      }, integer(1), USE.NAMES = TRUE)
    }
  )
)