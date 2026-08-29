# Changelog

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
