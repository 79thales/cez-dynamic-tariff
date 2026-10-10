# Oprava logu Home Assistantu z 10. 10. 2026

ČEZ: implementována oprava zdrojové karty a generátoru, regresní testy prošly.
Do běžícího HA se nic nezapsalo. Monitoring internetu je mimo otevřený projekt;
jeho oprava a akceptační kritérium pro obě chyby zůstávají nedokončené.

## Skutečná příčina ČEZ

Chybný výraz se nachází v `dashboard_template.json`, v hlavním pohledu, části
Aktuální cena, markdown kartě Cena odebrané kWh. Přímý konektor HA našel stejný
výraz v uloženém Overview `/lovelace/cez-dynamic-tariff`. Hodnota z `state_attr`
se předávala do `is_state(hdo, ...)` bez kontroly. HA poté volá `entity_id.lower()`;
pro `None` vzniká přesně nahlášený `TemplateError`. Testy reprodukovaly také
chyby pro číslo, boolean, seznam a objekt místo ID.

Původ atributu a inicializace byly ověřeny v aktuálním kódu:

1. `pricing.py` nastavuje výchozí `hdo_entity` na prázdný řetězec a úplné ocenění
   `pricing_enabled` na false. Výchozí režim proto cenový senzor vůbec nevytváří.
2. `config_flow.py:async_step_pricing` vybírá existující HDO binary senzor,
   senzor rozvrhu a binary senzor platnosti dat. Při zapnutém ocenění kontroluje
   existenci všech tří. Kandidáty ČEZ HDO navrhuje jen při jediném odpovídajícím
   zdroji; ID nejsou vynucena natvrdo. Ověření při nastavování nezaručuje existenci
   zdrojů během dalšího startu.
3. `__init__.py:async_setup_entry` vytvoří billing jen při zapnutém ocenění.
   `ElectricityBilling` převezme ID z options, data nebo výchozího profilu.
   `async_setup` přihlásí zdrojové stavové události i pro zatím neexistující ID.
   První výpočet proběhne před předáním senzorů do HA.
4. `billing.py:calculate` vrací `metadata.hdo_entity` z konfigurace i při
   nedostupných zdrojích. `sensor.py:extra_state_attributes` zveřejňuje metadata
   cenového senzoru. Samotné nedostupné HDO tedy nakonfigurované ID nemaže.
5. `state_attr` vrací `None`, když cenový senzor ještě neexistuje nebo nemá daný
   atribut. To je běžná startovní situace dashboardu a možná situace při reloadu.
   Explicitní null v nekorektně importované konfiguraci rovněž může dát `None`.
   Přesný okamžik původního logu nelze odlišit bez záznamu tehdejších stavů.
6. Generátor navíc kopíroval existující místní pohledy. Pouhá změna přibalené
   šablony by starou chybu v převzatém náhledu zachovala.

V manifestu není tvrdá závislost na `cez_hdo`; integrace používá veřejné stavy.
Dodatečné vynucování pořadí startu není potřeba: testy potvrdily odběr událostí,
pozdní vznik zdrojů a obnovu ceny bez změny API. Živou konfiguraci options ani
aktuální stav HDO konektor nečte; jejich skutečné hodnoty nebyly ověřeny.

Všechny výskyty `hdo_entity`, cenové zdroje, příklady a blueprinty byly prohledány.
Vadné dynamické volání bylo ve zdrojové kartě. Ostatní repozitářové šablony
`is_state` používají pevná ID. Živé automatizace nebyly úplně auditovány:
konektor jejich přehled načetl, u YAML balíčků monitoringu však vrací HTTP 404.

## Oprava a zachování funkcí

Karta ověří řetězec a celé entity_id včetně absolutního konce `\Z`. Odmítá
prázdné/neřetězcové hodnoty, mezery, velká písmena, nový řádek, chybějící tečku
i neplatná okrajová/dvojitá podtržítka. `states(hdo)` se zavolá teprve potom.
Pouze `on` je NT a `off` VT; chybějící, unknown a unavailable jsou „neznámé“.
Odběr Jinja začne sledováním cenového senzoru a po získání ID také HDO,
takže karta se sama obnoví po vzniku zdrojů.

`cezGuardHdoTemplates` při kopírování pohledů opraví původní volání s proměnnou
`hdo` a stavem on/off. Vrací nový JSON podstrom, původní dashboard nemění;
opakované použití je idempotentní. Složení hlavního pohledu, detailů a záloh,
kolizní kontroly i ochrana souběžných úprav zůstávají. Změna nevytváří senzory,
nemění unique_id/entity_id, cenové výpočty, DPH, distribuci, trial ani smlouvu.
Do běhu integrace nepřidává I/O, asyncio úlohy ani Recorder přístup.
Test Node → Jinja používá executor a timeout, takže ani jeho subprocess
neblokuje asyncio smyčku HA.

## Monitoring internetu: přesné umístění další práce

V repozitáři `C:\01.programovani\cez-dynamic-tariff` se producent
`internet_monitoring_report` nenachází. Byly pouze čteny nalezené zdroje
v jiném místním projektu; žádný jeho soubor se nezměnil.

Otevřete projekt **Home assitant**, cestu `C:\01.programovani\04.HA`, a složku
`proposals\internet-monitoring`. Obsahuje tyto skutečné zdroje:

- `internet_monitoring.py`: `report` a `export_files`, SQLite archiv a exporty;
- `weather_archive.py`: archiv počasí a jeho reportovací objekt;
- `internet_monitoring.yaml`, `automations.yaml`, `sensors.yaml`, `dashboard.yaml`;
- `ui-2026-10-09\package-after.yaml`: uložený snímek HA balíčku;
- `test_monitoring.py` a `test_weather.py`: existující testy tohoto projektu.

V uloženém balíčku událost vytváří automatizace `internet_monitoring_report_v1`
každou minutu a při startu HA, a také ruční `script.internet_monitoring_export`.
Obě volají `shell_command.internet_monitoring_export`, tedy
`python3 /config/internet_monitoring.py export`. Předávají pole `timestamp`,
`installed`, `periods`, `yesterday`, `events`, `days`, `last_event`, `weather`.
Report zahrnuje až 20 výpadků, 30 dnů, znovu první výpadek jako `last_event`,
počasí s až 24 archivními záznamy a pěti nejhoršími hodinami. Limity počtu
položek neomezují výsledný počet bajtů. V kódu události není kontrola 16 KiB
ani porovnání shodných souhrnů. Vyloučení reportovacího senzoru z Recorderu
neomezí velikost samostatné události na Event Busu.

To vysvětluje růst payloadu v dostupném zdroji. Pořadí největších položek,
přesný počet serializovaných bajtů a příčina dvojice reportů v 20:53:45/20:54:00
nejsou změřené: původní payload ani tehdejší databáze nejsou v tomto pracovním
prostoru. Uvedený balíček je snímek z 9. 10., jeho shoda s nyní běžícím HA není
potvrzena. Nejsou uváděny vymyšlené naměřené hodnoty ani provedené internetové testy.

Změna musí zahrnout producenta, oba způsoby vyvolání události, template senzory
a konzumenty `periods`, `events`, `days`, `weather` v dashboardu. Souhrn je třeba
měřit v bajtech, omezit na 16 KiB a historii číst z existujícího SQLite/exportu;
samotné odstranění polí by rozbilo současné karty. Detekce krátkých výpadků
patří do existujícího měřicího/stavového mechanismu. V tomto commitu se nic
z těchto částí nenahrazuje ani nepřesměrovává.

## Úplný seznam změněných souborů

| Soubor | Účel |
|---|---|
| `custom_components/cez_dynamic_tariff/dashboard_template.json` | Bezpečná HDO karta a český Jinja komentář. |
| `custom_components/cez_dynamic_tariff/frontend/dashboard-generator.js` | Oprava při převzetí místních pohledů. |
| `examples/hdo_status_card.yaml` | Hotová oprava jedné stávající karty. |
| `tests/test_dashboard_frontend.js` | Kopírování pohledů, rozsah změny a idempotence. |
| `tests_homeassistant/test_dashboard.py` | Typy/stavy HDO, chybějící senzor, živý odběr šablony, všechny markdown karty, JS → Jinja a YAML. |
| `tests_homeassistant/test_hdo_lifecycle.py` | Start bez HDO, opožděné zdroje, reload, ID a ceny NT/VT v obou režimech. |
| `docs/dashboard-generator.md` | Údržba a nasazení opravené karty. |
| `CHANGELOG.md` | Popis opravy bez vydání nové verze. |
| `docs/ha-2026-10-log-fixes.md` | Tento audit, výsledky a hranice ověření. |

## Výsledky ověření

| Kontrola | Výsledek |
|---|---|
| Reprodukce původní HDO karty | Chyba potvrzena: 11 regresních scénářů selhalo, 5 platných/stavových prošlo. |
| Celá sada `tests_homeassistant` | **PASS: 71** v HA **2025.1.4**, plugin 0.13.205, Python 3.12.14. |
| `python -m unittest discover -s tests -v` | **PASS: 97**. |
| `node --test tests/test_dashboard_frontend.js tests/test_release_workflow.js` | **PASS: 21**. |
| `ruff check custom_components tests tests_homeassistant scripts` | **PASS**. |
| `python -m compileall -q custom_components tests tests_homeassistant scripts` | **PASS**. |
| `git diff --check` | **PASS**. |
| HA 2026.10.x runtime | **NESPUŠTĚNO**; viz důvod níže. |
| Produkční restart/reload a frontend v běžícím HA | **NESPUŠTĚNO**; nic nebylo nasazeno. |
| Monitoring: krátký/dlouhý report, velká historie, nedostupný cíl, opakování, velikost, detekce a aktualizace dashboardu | **NESPUŠTĚNO**; jiný projekt a nezměněný producent. |

Lokální HA testy vyžadovaly povolení Windows loopback socketpair; původní
sandbox jej blokoval při vytvoření asyncio smyčky. Lokální pomocný runner
ponechal ochranu spojení testů mimo loopback. Testy nevyvolávají výpadek
internetu a neovládají produkční HA. Zůstala upozornění staršího testovacího
pluginu na pytest konfiguraci/import; samotné testy neselhaly.

Testy obsahují skutečné načtení config entry jako po restartu, pozdní vznik
HDO a skutečný unload/setup při reloadu. Nejde o restart celého procesu HA.
Kontrola trial, DPH, distribuce a účtování je součástí stávající plné sady.

## Kompatibilita, rizika a nasazení

Cíl je HA 2026.10.x. Úpravy používají dokumentované
[čtení stavu](https://www.home-assistant.io/template-functions/states/) a
[regex_match](https://www.home-assistant.io/template-functions/regex_match/)
s Jinja testem `is string`; v upraveném runtime kódu není nové ani zastaralé
backend API. Z těchto podkladů plyne očekávaná kompatibilita, nikoli potvrzený
runtime test na cílové verzi.

Veřejná metadata PyPI při kontrole uváděla HA **2026.10.1**. Projektový
`scripts/resolve_latest_ha.py` však skončil chybou
`No matching test plugin found for latest stable Home Assistant 2026.10.1`.
Dostupný lokální runtime má Python 3.12.14 a HA 2025.1.4, takže úspěch této sady
nelze označit jako ověření 2026.10. CI nad nejnovější stabilní verzí musí projít
po dostupnosti odpovídajícího testovacího prostředí. Bylo použito veřejné
[PyPI Home Assistant](https://pypi.org/project/homeassistant/) a stávající resolver.

Pro současný uložený dashboard nahraďte pouze kartu Cena odebrané kWh YAML
z `examples/hdo_status_card.yaml`. Při auditu měla cesta k jejímu obsahu podobu
`/views/15/sections/0/cards/1/content`; číslo pohledu se po změně pořadí může lišit.
Kartu vyhledejte podle cesty pohledu `cez-dynamic-tariff` a nadpisu Aktuální cena.
Uložení dashboardu nepotřebuje restart ani reload integrace. Nahrajte také
opravený zdroj generátoru a přibalenou šablonu pro budoucí náhledy; po změně
JS obnovte prohlížeč bez cache, protože verze manifestu se tímto commitem nemění.
Pokud aktualizujete celou integraci standardním postupem, načtěte ji znovu.

Zbývá ověřit reálný restart/reload na HA 2026.10.x a log po nasazení. Stávající
uložená karta se samotnou aktualizací souborů automaticky nezmění. Upozornění
`internet_monitoring_report` tato oprava ČEZ neřeší; je nutné pokračovat v přesně
uvedeném projektu. Celkové akceptační kritérium pro obě chyby zatím splněno není.
