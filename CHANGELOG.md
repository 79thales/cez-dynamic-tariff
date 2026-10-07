# Changelog

## 0.5.1 – 2026-10-07

### Čeština

- Instalační příloha `cez_dynamic_tariff.zip` pro HACS a odznaky celkových stažení i posledního vydání v README. Počítání začíná touto verzí; zahrnuje stažení balíčku a aktualizace, nikoli unikátní uživatele.
- Horní počet v HACS patří vybranému vydání. Zdrojové archivy, instalace výchozí větve a ukázkové blueprinty se do odznaků nezapočítávají; starší stažení bez přílohy nelze zpětně dopočítat.
- Automatické balíčkování z přesného Git commitu nejdříve vytvoří koncept release s ZIPem a českými i anglickými poznámkami. Kontroluje verzi, strukturu archivu a nepřepisuje zveřejněné přílohy.
- Závislost `holidays>=0.106` odstraňuje konflikt hlášený aktuálním Hassfestem a umožňuje následovat aktualizace této knihovny v Home Assistantu. CI ověřuje minimální podporovanou verzi `0.106`.
- Regresní testy ověřují české svátky v letech 2025–2027, Velikonoce, přechod přes Nový rok a volbu tarifu se skutečnou knihovnou. Testy kalendáře prošly s původní i novou verzí.
- CI při každém běhu doplní test skutečně nejnovější stabilní verze Home Assistantu z PyPI, s odpovídajícím testovacím pluginem; vedle dosavadních testovaných verzí. Nesoulad testovacího pluginu skončí chybou, nikoli tichým návratem ke staršímu nebo beta HA.
- Sjednocené pořadí a vzhled odznaků s ostatními integracemi; souhrnný odznak Validation a absolutní odkaz na logo pro správné zobrazení v HACS. Odznak Home Assistant uvádí minimální podporovanou verzi.
- Bez změn tarifních výpočtů, rozvrhů, entit nebo konfigurace; bez telemetrie. Starší vydání si zachovávají původní způsob instalace.

### English

- A HACS installer asset, `cez_dynamic_tariff.zip`, and README badges for total and latest-release installer downloads. Counting starts with this version and includes downloads and updates, not unique users.
- HACS's download indicator covers the selected release. Source-code archives, default-branch installations and example blueprints are excluded from the badges; earlier downloads without an installer asset cannot be recovered.
- The packaging workflow builds from the exact Git commit and first creates a draft with the installer and Czech/English release notes. It validates the manifest version and archive layout and never overwrites published assets.
- Changed the dependency to `holidays>=0.106` to resolve the conflict reported by current Hassfest validation and allow it to follow Home Assistant's library updates. CI verifies the minimum supported version, `0.106`.
- Added regressions for Czech public holidays in 2025–2027, Easter, year boundaries and tariff selection using the real library. Calendar tests passed with both the previous and updated dependency.
- Each CI run also tests the actual latest stable Home Assistant from PyPI with a matching test plugin, alongside the existing pinned environments. A missing matching plugin fails clearly instead of silently testing an older or beta HA release.
- Unified badge order and styling across the integrations, an aggregate Validation badge and an absolute logo URL for HACS rendering. The Home Assistant badge states the minimum supported version.
- No changes to tariff calculations, schedules, entities or configuration, and no added telemetry. Older releases retain their original installation method.

## 0.5.0

- nový timestamp senzor `current_cheap_end` ukazuje konec aktuálního souvislého levného období včetně navazujících pásem a půlnoci; mimo levné období nebo bez konce v osmiden­ním výhledu vrací neznámou hodnotu,
- opravený původ tarifních dat při návratu k vestavěnému rozvrhu po neplatném uloženém rozvrhu,
- DST testy vyžadují skutečná IANA data i na Windows; doplněné testy konfigurace a resetu přes skutečné Home Assistant rozhraní,
- zachovaná stávající ID entit, konfigurace, formát rozvrhů, cenové výpočty a chování dosavadních senzorů.

### English

- Added the `current_cheap_end` timestamp sensor for the end of the active continuous cheap period, including adjacent bands and midnight. It returns unknown when inactive or when no end is found within eight days.
- Corrected schedule provenance when invalid saved schedules fall back to bundled data.
- Required real IANA timezone data for DST tests on Windows and added configuration/reset tests through Home Assistant's flow APIs.
- Preserved existing entity IDs, configuration, schedule format, price calculations, and existing sensor behavior.

## 0.4.4

- přidané regresní testy pro podzimní přechod na standardní čas, přesné hranice tarifního rozvrhu, záporný modifier, nulovou základní cenu a stabilní čtyřmístné zaokrouhlení,
- potvrzená kompatibilita lifecycle testů s Home Assistant 2025.1.4 a 2026.8.3,
- beze změn runtime logiky, ID entit, konfigurace, formátu rozvrhů a automatizačního chování.

## 0.4.3

- anglický přehled přesně rozlišuje tarifní rozvrh, tarifní období, procentní modifier, vypočtenou obchodní cenu a skutečnou smluvní nebo tržní cenu,
- zpřesněné anglické názvy entit a texty konfiguračního flow pro mezinárodní HACS review,
- výslovně uvedené, že integrace nestahuje živé ceny ani smluvní data,
- beze změn runtime logiky, ID entit, konfigurace, formátu rozvrhů a automatizačního chování.

## 0.4.2

- přidaný profesionální anglický přehled funkcí, zdrojů tarifních dat, omezení, instalace a konfigurace pro HACS review,
- opravený neplatný odkaz na My Home Assistant badge a nahrazené natvrdo uvedené číslo verze dynamickým odkazem na aktuální release,
- odstraněný zavádějící konceptuální obrázek s funkcemi, které integrace neposkytuje,
- zpřesněná anglická metadata repozitáře a poznámky k vydání.

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
