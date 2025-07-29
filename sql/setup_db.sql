-- slouží pro vytvoření systému tabulek, do kterých se budou ukládat postupně vytěžované informace
-- datum: 2025-06-21

-- -----------------------------------------------------
-- Schema vost_data
-- -----------------------------------------------------

-- -----------------------------------------------------
-- Schema vost_data
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `vost_data` DEFAULT CHARACTER SET UTF8MB4 COLLATE utf8mb4_czech_ci;
USE `vost_data` ;

-- -----------------------------------------------------
-- Table `vost_data`.`kampan`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `vost_data`.`kampan` (
  `idKampan` INT NOT NULL AUTO_INCREMENT,
  `nazev` VARCHAR(255) NOT NULL,
  `popis` TEXT NULL,
  PRIMARY KEY (`idKampan`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = UTF8MB4
COLLATE = utf8mb4_czech_ci;


-- -----------------------------------------------------
-- Table `vost_data`.`postBSky`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `vost_data`.`postBSky` (
  `idPost` INT NOT NULL AUTO_INCREMENT,
  `idKampan` INT NOT NULL,
  `text` TEXT NOT NULL,
  `datum` DATETIME NOT NULL,
  `autor_did` VARCHAR(255) NOT NULL,
  `autor_handle` VARCHAR(255) NOT NULL,
  `sentiment` TEXT NOT NULL,
  `entity` JSON NULL,
  `fake_news_score` FLOAT NULL,
  `language` VARCHAR(45) NULL,
  `krizova_situace` TEXT NULL,
  PRIMARY KEY (`idPost`),
  INDEX `fkKampan_idx` (`idKampan` ASC) VISIBLE,
  CONSTRAINT `fkKampan`
    FOREIGN KEY (`idKampan`)
    REFERENCES `vost_data`.`kampan` (`idKampan`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = UTF8MB4
COLLATE = utf8mb4_czech_ci;


-- -----------------------------------------------------
-- Table `vost_data`.`hashtagy`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `vost_data`.`hashtagy` (
  `idHashtag` INT NOT NULL AUTO_INCREMENT,
  `hashtag` VARCHAR(100) NOT NULL,
  PRIMARY KEY (`idHashtag`))
ENGINE = InnoDB
DEFAULT CHARACTER SET = UTF8MB4
COLLATE = utf8mb4_czech_ci;


-- -----------------------------------------------------
-- Table `vost_data`.`hashtagPostBShy`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `vost_data`.`hashtagPostBShy` (
  `idHashTag` INT NOT NULL,
  `idPost` INT NOT NULL,
  PRIMARY KEY (`idHashTag`, `idPost`),
  INDEX `fkPost_idx` (`idPost` ASC) VISIBLE,
  CONSTRAINT `fkHashTag`
    FOREIGN KEY (`idHashTag`)
    REFERENCES `vost_data`.`hashtagy` (`idHashtag`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT `fkPost`
    FOREIGN KEY (`idPost`)
    REFERENCES `vost_data`.`postBSky` (`idPost`)
    ON DELETE CASCADE
    ON UPDATE CASCADE)
ENGINE = InnoDB
DEFAULT CHARACTER SET = UTF8MB4
COLLATE = utf8mb4_czech_ci;
