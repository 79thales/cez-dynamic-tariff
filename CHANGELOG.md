# Changelog

## 2.0.0

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
