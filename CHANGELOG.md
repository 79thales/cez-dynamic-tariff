# Changelog

## 0.4.1

- lifecycle testy ověřují bezpečné obnovení stavů entit po odpojení a opětovném načtení integrace,
- opravená importní cesta pro testy spouštěné s Home Assistantem,
- GitHub Actions používají aktuální Node.js 24.

## 0.4.0

- reload po změně nastavení nyní používá plný lifecycle config entry v Home Assistantu a nehromadí update listenery,
- vestavěný rozvrh má dohledatelnou revizi, oficiální zdroj ČEZ a odpovídající atributy entit,
- CI ověřuje skutečný setup, opakovaný reload a unload na nejstarší podporované i aktuální stabilní verzi Home Assistantu a publikuje coverage,
- přidané blueprinty pro levné a super levné pásmo a pro reakci na drahé pásmo,
- prezentační obrázek je začleněný jako jasně označený koncept rozšířeného energetického dashboardu,
- opravené číslo aktuální verze v README.

## 0.3.1

- doporučený Lovelace dashboard je převedený na responzivní pohled Sections s hustým rozmístěním sekcí,
- dnešní a zítřejší mapa zobrazuje každé tarifní okno na samostatném řádku přímo z dynamického atributu `schedule`,
- právě aktivní tarifní okno je v dnešní mapě zvýrazněné,
- aktuální kategorie tarifu se odvozuje ze všech čtyř binárních senzorů a doplňuje praktické doporučení,
- další změna tarifu, další levné okno a všechny nastavitelné prahy mají samostatné přehledné karty,
- dokumentace a hotový příklad dashboardu jsou vzájemně synchronizované.

## 0.3.0

- přidané senzory nejbližší skutečné změny tarifu a procentní změny, která po ní začne,
- přidaná dynamická mapa tarifu na zítřek včetně rozvrhu, legendy, sezóny a typu dne,
- přidané binární senzory levného a super levného pásma,
- sezóna a typ dne nyní obsahují stabilní strojové kódy v atributech bez změny dosavadních českých stavů,
- možnosti integrace jsou rozdělené na základní nastavení, prahy a časové rozvrhy; obnovení výchozích rozvrhů vyžaduje samostatné potvrzení,
- přidané stažení diagnostiky integrace a použití typovaného `ConfigEntry.runtime_data`,
- prahové senzory jsou označené jako diagnostické entity,
- rozšířené regresní testy pokrývají veřejné entity, překlady, svátky, půlnoc, přechod sezóny, časové pásmo a nové výpočty,
- aktualizovaný doporučený dashboard zobrazuje další změnu, levná pásma a zítřejší mapu.

## 0.2.3

- výchozí ID všech senzorů a binárních senzorů se nyní explicitně odvozují z interních stabilních klíčů, nikoli z přeloženého názvu entity,
- senzor aktuální změny ceny se při nové registraci vytvoří jako `sensor.cez_dynamic_tariff_current_modifier`, nikoli jako `sensor.cez_dynamic_tariff_price_change`.

## 0.2.2

- všechny senzory a binární senzory jsou přiřazené ke společnému zařízení ČEZ Dynamic Tariff, takže nové výchozí ID jednotně používá prefix `cez_dynamic_tariff_`.

## 0.2.1

- přidaný hotový dynamický dashboard v `examples/dashboard.yaml`; mapa a legenda se přizpůsobují upraveným časům, procentům i novým pásmům.

## 0.2.0

- časová pásma lze přidávat, odebírat a měnit ve formátu `HH:MM=změna_v_%`,
- všechny čtyři výchozí rozvrhy jsou ověřené proti zveřejněné tabulce časových pásem a chráněné regresním testem,
- zachovaná kompatibilita se starším uloženým formátem obsahujícím pouze začátky oken,
- nápověda v Home Assistantu i README vysvětluje pásma, prahy, validaci a obnovení výchozího rozvrhu,
- doporučený dashboard dynamicky zobrazuje mapu, legendu, všechny čtyři prahy a stav drahého i velmi drahého pásma,
- mapa a legenda tarifu se automaticky přizpůsobí libovolným procentním změnám a novým pásmům,
- doplněný samostatný práh velmi drahého pásma `+25 %`, jeho senzor a binární senzor,
- chybové hlášky možností integrace mají vlastní české a anglické překlady,
- při chybě ve formuláři zůstane zachovaný rozepsaný uživatelský vstup.

## 0.1.9

- integrace je správně klasifikovaná jako služba a zobrazuje se v **Nastavení → Zařízení a služby → Integrace**,
- opravené lokalizované názvy entit bez textu `UndefinedType._singleton`,
- doplněný překlad hlášky při pokusu přidat druhou konfiguraci.

## 0.1.8

- načtení českých svátků probíhá mimo hlavní event loop Home Assistantu.

## 0.1.7

- rozvrhy časových oken lze upravit přímo v možnostech integrace v Home Assistantu,
- přidané obnovení výchozích rozvrhů vestavěných v projektu.

## 0.1.6

- opravené odkazy na repozitář, dokumentaci, issue tracker a HACS workflow.

## 0.1.5

- lokalizované názvy entit v češtině a angličtině,
- bezpečnější práce s lokálním časem Home Assistantu,
- validace základní ceny v konfiguračním flow,
- přidaná kontrola Ruff a kompilace Pythonu v CI,
- aktualizovaná dokumentace instalace přes HACS.

## 0.1.4

- předchozí vydání integrace.
