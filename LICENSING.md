# Licenční audit – cez-dynamic-tariff

Audit dne 2026-10-12, výchozí commit `c0ea5085aa8aae9c4f3e4a400016f48edab578c4`, změna 1.0.8 → 1.0.9.

## Autorství a rozsah

Kontrola všech lokálně stažených větví a tagů (`git shortlog -sne --all`, autorů a committerů) a GitHub contributors našla pouze Jiřího Dvořáka / 79thales; e-mailové varianty se liší velikostí písmen. GitHub je pouze committer webových změn, nikoli další autor. Kontrola hlaviček a odkazů ve zdrojích neodhalila dalšího uvedeného autora vlastního kódu.

Kontrolovány byly LICENSE, README, changelog, manifest, HACS metadata, balicí skripty, workflows, případná Python/JS metadata, zdrojové hlavičky, frontend a evidence brand PNG v historii. Nebyly nalezeny vložené fonty ani další knihovny mimo níže uvedené. Brand soubory mají v dostupné historii autora projektu a nemají zvláštní oznámení cizí licence. Samotná historie nemůže doložit původ mimo repozitář; nebyla nalezena konkrétní indicie nejasného vlastnictví významné části.

## Cizí obsah a závislosti

Nebyl nalezen vložený cizí kód ani samostatně licencované fonty.

Importované závislosti: holidays (MIT), pypdf (BSD-3-Clause). Importy z Home Assistantu, jeho prostředí a standardní knihovny nemění licence těchto závislostí. Python balíčky se do ZIPu nevkládají.

Kompatibilita MIT/Expat, BSD-3-Clause a Apache-2.0 s GPLv3 byla ověřena v [přehledu GNU](https://www.gnu.org/licenses/license-list.html). Nebyla nalezena licenční překážka přechodu vlastního projektu.

## Nová distribuce

Kořenový i instalační LICENSE obsahují nezměněný [oficiální text GPLv3](https://www.gnu.org/licenses/gpl-3.0.txt). Volbu **GPL-3.0-only** a copyright stanoví README a NOTICE.txt; příklady v závěru oficiálního textu licence tuto volbu nenahrazují. NOTICE.txt uvádí i zdroj konkrétního tagu. Existující balicí skripty automaticky zahrnou oba soubory z adresáře integrace.

Staré commity, tagy, release, jejich instalační soubory a původní licence se nemění. Provozní logika, API, entity a dashboardy se neupravují. Do manifestu ani hacs.json se nepřidává pole licence. Projekt nemá zavedené plošné SPDX hlavičky; nové se nevkládají.
