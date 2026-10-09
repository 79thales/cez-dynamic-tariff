# Changelog

## 1.0.4 – 2026-10-09

**Vyžaduje nainstalovanou a nakonfigurovanou integraci [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce).**

### Čeština

- Rozšíření výrazného updatu **ČEZ Dynamic Tariff & Accounting**: přehledná karta záloh po měsících, editace částky, částečně zaplacené částky, zbývajícího doplatku a jednotlivé potvrzení plné zálohy. Součást integrace; nevyžaduje další instalaci karty přes HACS.
- Volitelné automatické potvrzení vždy k prvnímu dni měsíce, výchozí vypnuté. Zapnutí uprostřed měsíce začne příštím měsícem. Nepotvrzuje starou historii ani nezadané zálohy, nepřepisuje ruční opravy a částečné úhrady; opakování a restart nezapočtou platbu dvakrát. Automatické označení je odlišitelné od ručního potvrzení a neověřuje bankovní platbu.
- Samostatná volba správného elektroměru pro účetnictví. Přebírá existující statistiky a náklady jen ze shodného zdroje; původní entity a zdroj původního monitoringu zůstávají zachované.
- Editace záloh aktualizuje výpočet bez zbytečného načítání historie Recorderu a bez restartu integrace. Dosavadní roční součet se nerozpočítává na vymyšlené měsíce. Soukromá finanční data nejsou obsahem instalačního balíčku.

### English

Requires the installed and configured [ČEZ HDO integration by Cmajda](https://github.com/Cmajda/ha_cez_distribuce).

- Extends the substantial **ČEZ Dynamic Tariff & Accounting** update with a bundled monthly advances card: edit amounts, partial payments, remaining balances and confirm each payment.
- Optional first-of-month automatic confirmation, disabled by default. Mid-month opt-in starts next month. No retroactive history confirmation, unknown amounts or duplicate payments; manual corrections and partial payments are retained. Automatic bookkeeping is labeled and does not verify bank transactions.
- Independent accounting import-meter selection reuses existing statistics, without changing original entities or their source. Monetary costs from a different meter are not reused.
- Payment edits refresh calculations without rereading Recorder history or reloading the integration. Annual aggregates are never distributed to invented months; installers contain no private financial data.

## 1.0.3 – 2026-10-09

**Vyžaduje nainstalovanou a nakonfigurovanou integraci [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce).**

### Čeština

- Oprava ukládání měsíčních záloh v nové části Accounting. Home Assistant nyní správně otevře i odešle měsíční formulář; chyba „Unknown error occurred“ bránila zapnutí účetnictví a zpětného dopočtu.
- Regresní ověření celého průchodu pomocí skutečného správce konfiguračních kroků Home Assistantu. Zachovává původní nastavení a rozlišuje nezadané, zaplacené a plánované měsíce.
- Navazuje na výrazný update **ČEZ Dynamic Tariff & Accounting** ve verzi 1.0.2. Původní entity a jejich ID zůstávají zachovány.

### English

Requires the installed and configured [ČEZ HDO integration by Cmajda](https://github.com/Cmajda/ha_cez_distribuce).

- Fix monthly advance setup in Accounting: dispatch the monthly form through Home Assistant's flow manager. The previous “Unknown error occurred” prevented enabling accounting and historical backfill.
- Regression coverage exercises the complete managed options flow, preserving existing settings and missing, paid and planned months.
- Continues the substantial **ČEZ Dynamic Tariff & Accounting** update in 1.0.2 without changing original entities or their IDs.

## 1.0.2 – 2026-10-09

**Vyžaduje nainstalovanou a nakonfigurovanou integraci [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce).** Plná cena, zpětné ocenění a cenový výhled používají její veřejné údaje NT/VT, rozvrh a platnost. Původní samostatné procentní senzory tuto závislost nemají.

### Čeština

**Výrazné rozšíření aktualizace 1.0.0: ČEZ Dynamic Tariff & Accounting.** Doména a všech 39 původních entit, jejich ID, unique ID a význam zůstávají zachovány. Účetnictví přidává 18 volitelných senzorů.

- Nastavitelné zúčtovací období, výchozí 1. duben až 31. březen; zálohy jako úplný součet nebo jednotlivé měsíce se skutečným označením zaplacení.
- Zpětný odběr používá existující opravené statistiky Recorderu. Již spočítané náklady se převezmou; chybějící se ocení jen při dostupném historickém HDO, cenách a smluvním datu aktivace. Dnešek se doplňuje od půlnoci pomocí existujících pětiminutových statistik, s veřejně uvedeným časem pokrytí. Žádné nové statistiky se do Recorderu neimportují a původní náklady se nepřepisují.
- Rozpis odběru, denního podílu jističe a dalších stálých plateb, známých příjmů ze sdílení a čistých nákladů. Zahrnutí stálých plateb zůstává volitelné.
- Ruční odečtení již vypočtené finanční statistiky EDC, včetně `energy_revenue_statistic_id`; bez druhého násobení sdílených kWh cenou a bez přičítání stejného příjmu vícekrát. Zpožděná data se nepřiřazují k dnešku.
- Převzetí ověřeného odečtu dodavatele a předchozích vyúčtování bez přeocenění. Měsíční profil spotřeby používá úplné historické dny; chybějící měsíce mohou doplnit údaje ověřené faktury. Nastavení a soukromé finanční údaje se nezveřejňují v diagnostice.
- Odhad celého období a přeplatku/nedoplatku odděluje zaplacené zálohy od plánovaných. Chybějící historie, ceníky a zálohy se nepovažují za nulu. Odhad budoucích nákladů používá sezónní odběr a průměr nynějšího dvoudenního výhledu; budoucí sdílení ani změny cen tím nejsou předpovězené.
- Rozlišení finálního tarifu a tarifu na zkoušku. Na zkoušku účetnictví používá standardní fakturované NT/VT ceny a nezapočítává neověřenou budoucí vratku. ČEZ pro ni používá váženou obchodní cenu a celé zkušební období. Dynamická procenta se nikdy neaplikují na distribuci, daně ani stálé platby.
- [Nastavení, formát historie a omezení odhadu](docs/accounting.md). ČEZ HDO se nemění ani neforkuje; původní integrace a účetnictví EDC se používají jako zdroje.

### English

**A substantial extension of the 1.0.0 update: ČEZ Dynamic Tariff & Accounting.** Requires the installed and configured [ČEZ HDO integration by Cmajda](https://github.com/Cmajda/ha_cez_distribuce) for public NT/VT schedules and validity. All 39 existing entities retain their IDs, unique IDs and meaning; accounting adds 18 optional sensors.

- Configurable billing periods (default April–March), annual advance aggregates or individually recorded monthly planned/paid payments.
- Reuses corrected Recorder import increments and existing monetary costs. Only missing costs are reconstructed where historical HDO, prices and contractual dates are available. Today is backfilled from midnight using existing five-minute statistics; coverage timestamps and gaps are explicit. Does not rewrite or import energy statistics.
- Separate import costs, optional calendar-day standing fees, existing EDC monetary sharing income and net costs. No duplicate energy-to-revenue calculation; delayed income is not assigned to today.
- Verified provider checkpoints and settled bills are reused without repricing. Seasonal demand comes from complete historic days or verified monthly invoice readings. Private financial settings are redacted from diagnostics.
- Full-period demand/cost and surplus/deficit estimates distinguish paid from planned advances. Missing inputs are not zero. Future costs use seasonal demand and the current two-day mean price; future income and price changes are not predicted.
- Separate final and trial contract accounting. Trials retain standard invoiced NT/VT prices and exclude unverified future refunds, whose supplier calculation uses a weighted trading price over the trial period. Modifiers never apply to distribution, taxes or standing fees.
- See [accounting setup and limitations](docs/accounting.md). Reuses existing ČEZ HDO and EDC data without modifying or forking either integration.

## 1.0.1 – 2026-10-09

### Čeština

**Rozšíření výrazné aktualizace 1.0.0 o načítání ceníků ČEZ.**

- Nová volba **Importovat ceník ČEZ z PDF** v nastavení integrace: nahrání souboru nebo přímý HTTPS odkaz na PDF na `www.cez.cz`.
- Rozpoznání sloupce distribuční sazby a platby pro zvolený jistič, obchodních cen VT/NT, distribuce, daně, systémových služeb, stálých plateb a POZE. Částky s DPH se převádějí z Kč/MWh na Kč/kWh.
- Před uložením se zobrazí editovatelná kontrola všech částek, zdroj a účinnost. Uloží se také otisk PDF. Import zachovává původní entity, základní obchodní cenu, rozvrhy a nastavení HDO. Historické náklady se nepřepočítávají.
- Podporovaný je standardní textový ceník domácností ČEZ Prodej / ČEZ Distribuce s jedním cenovým obdobím a 21 % DPH. Skeny, nejednoznačné tabulky, chybějící položky, neshodné součty a ceníky s budoucí účinností se odmítají bez změny cen. Při nenulovém POZE podle jističe je nutný roční odběr pro odhad efektivní sazby a následné roční vyrovnání.
- Závislost nového cenového profilu na [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce): používá existující stav NT/VT, rozvrh a platnost. ČEZ HDO se nemění ani neforkuje. Původní funkce Dynamického tarifu zůstávají samostatné.
- Import se zpracovává lokálně v Home Assistantu, bez odesílání PDF do externích AI služeb. Nové závislosti: `file_upload` a `pypdf==6.19.0`.
- Testy ověřují rozpoznání cen a jističe, DPH a jednotky, kontrolu součtů, potvrzení před uložením, zachování starých nastavení a omezení stahování.

### English

**Extends the major 1.0.0 update with ČEZ PDF price-list imports.**

- Integration options can now import an uploaded PDF or a direct HTTPS PDF URL on `www.cez.cz`.
- Reads the selected distribution-rate column and breaker fee, VT/NT trading and distribution prices, tax, system services, standing charges and POZE. VAT-inclusive CZK/MWh is converted to CZK/kWh.
- Editable review of every rate, source and effective dates before saving; the PDF digest is retained. Original entities, base trading price, schedules and HDO settings are preserved. Historical costs are not recalculated.
- Supports the standard single-period text-based ČEZ Prodej / ČEZ Distribuce household table with 21% VAT. Scans, ambiguous tables, missing cells, inconsistent totals and future-effective lists are rejected without changing rates. Nonzero capacity POZE requires an annual-import estimate for an effective rate, with annual reconciliation.
- Full pricing depends on the installed [ČEZ HDO integration by Cmajda](https://github.com/Cmajda/ha_cez_distribuce), reusing public NT/VT, schedule and validity states without modifying or forking it. Original Dynamic Tariff functions remain independent.
- PDF parsing is local to Home Assistant; no PDF is sent to external AI services. Added dependencies: `file_upload` and `pypdf==6.19.0`.
- Tests cover rate/breaker recognition, VAT and units, totals, confirmation before saving, preservation of existing settings and restricted downloads.

## 1.0.0 – 2026-10-09

### Čeština

**Výrazná hlavní aktualizace:** plná cena elektřiny, náklady a úspory. Nový cenový profil vyžaduje nainstalovanou a nakonfigurovanou integraci [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce) pro stav NT/VT, rozvrh a platnost dat. Původní funkce Dynamického tarifu fungují samostatně.

- Volitelný profil D57d / 3×25 A pro celkovou cenu včetně DPH, distribuce a regulovaných složek.
- Napojení na veřejné entity existující integrace ČEZ HDO bez jejího forku nebo změn.
- Výběr skutečné ceny s Dynamickým tarifem nebo bez něj a souběžné porovnání obou variant.
- Denní náklady a volitelné zahrnutí poměrné části jističe a ostatních stálých poplatků.
- Cenový výhled do konce zítřka, nejlevnější čas a další změna celkové ceny.
- Uložené odhady nákladů, dosažené a teoretické úspory ze skutečného importu.
- Původních 21 entit zachováno; cenový profil přidává 18 nových senzorů.

### English

**Major update:** full electricity pricing, costs and savings. The new price profile requires an installed and configured [ČEZ HDO integration by Cmajda](https://github.com/Cmajda/ha_cez_distribuce) for NT/VT state, schedule and data validity. Original Dynamic Tariff functions remain independent.

- Optional VAT-inclusive full electricity pricing with distribution, tax and regulated charges; a D57d / 3×25 A preset from the 30 January 2026 ČEZ two-year promotion price list.
- Reuses public state, validity and schedule entities of the installed ČEZ HDO integration, without forking or modifying it.
- Select actual pricing with or without Dynamic Tariff, with both variants always available for comparison.
- Daily import costs with optional calendar-day allocation of breaker and other standing fees.
- Today/tomorrow price forecast, cheapest known time and next total-price transition.
- Persisted meter-based estimates of costs, signed achieved savings and separately labelled theoretical shifting potential. Missing prices remain unpriced; historical lifetime readings are never charged on setup.
- Preserves all 21 original entities, IDs and their meaning; the optional profile adds 18 sensors.
- Enable the new price profile in integration options after updating; existing configurations keep their behavior by default.

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

