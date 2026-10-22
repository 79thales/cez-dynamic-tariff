# Audit a ověření vydání 1.1.0

Datum: 22. 10. 2026. Rozsah: dvě cenové strategie, import obou nových ceníků,
aktivace, semafory, dashboard, účetní návaznosti a příprava českého vydání.
Nejde o audit tokenové spotřeby ani o nasazení do živého Home Assistantu.

## Výsledek

Oba režimy jsou implementované a verze manifestu je **1.1.0**. Lokální kontroly
neodhalily zbývající blokující vadu v otestovaném prostředí. Připraven je
instalační ZIP a české poznámky k vydání. GitHub Release není publikovaný.
HACS, Hassfest a testy současné stabilní verze HA v CI zatím nejsou ověřené.

Pracovní strom obsahoval před zahájením rozsáhlé rozpracované změny účetnictví,
archivu, frontendů a dokumentace. Byly zachované; neproběhl reset, přepis
hlavní větve ani commit/tag v hlavním repozitáři. ZIP obsahuje současný runtime
včetně těchto změn a byl porovnán se skutečnými soubory pracovního stromu.

## Vstupní zjištění a jejich vyřešení

| Zjištění | Řešení a důkaz |
| --- | --- |
| Původní cena vznikala násobením standardní dodávky procentem. | Dvě strategie mají společný časový výpočet. Pevná dodávka se použije přímo; ruční kontrola a regresní testy ověřují vyloučení dvojího procentního přepočtu. |
| Import očekával dvě obchodní ceny VT/NT a jiné číslování řádků. | Samostatné rozpoznání nových produktů, čtyři rozvrhy a regulované řádky, kontrola osmi celkových cen. Obě uživatelské přílohy byly lokálně úspěšně přečtené pro D57d, 3×25 A. |
| Oba produkty mají nezávislou obchodní a distribuční část. | Přímá dodávka se kombinuje s aktuálním HDO; pevný profil uchovává vlastní poplatky a roční odběr. Standardní reference se nepřepisuje. |
| Uložený nový profil nesmí znamenat okamžitou změnu smlouvy. | Import pouze přidává profil; volič nebo samostatný formulář explicitně aktivuje režim a vybraný produkt. Budoucí čas vyžaduje offset. |
| Změna ceny nesmí přecenit minulou spotřebu. | Cenové události obsahují podklady před/po změně. Rozpracovaný odečet se ukládá s původními cenami a rozdělí podle přesné aktivace. |
| Nový otisk cen by mohl odříznout dříve ověřené archivované náklady. | Hodiny celé před aktivací mohou převzít odpovídající archiv. Ověřuje se energie, identita elektroměru/HDO/finančního zdroje a časové pásmo. Regrese pokrývá změnu ceny a purge HDO/Recorderu. |
| Semafory a automatizace byly navázané na procentní entity. | Původní entity a význam zůstávají. Tři nové senzory popisují aktivní strategii; žádné automatizace se samy nepřepojují. |
| Víkend nemá nejdražší pásmo a starší uživatel může mít vypnuté svátky. | Pevné úrovně se třídí ze všech čtyř rozvrhů a pevný smluvní ceník vždy respektuje české svátky. Procentní preference zůstává zachovaná. |
| Generátor přebírá místní pohledy. | Šablona, Python vazby registru a JS převzetí pohledů se změnily společně. Známé cenové karty se aktualizují, volič vzniká právě jednou; jiné místní karty a všechny tři pohledy se zachovají. |
| Sestavení vyžadovalo českou i anglickou sekci. | Sestavení přijímá českou sekci a exportuje pouze ji. Historický changelog zůstává zachovaný. Technické postupy z README nejsou součástí release notes. |

## Přehled důležitých částí kódu

- `band_pricing.py`: oddělené profily a neměnné cenové revize. Částky jsou
  Kč/kWh nebo Kč/měsíc včetně DPH. Aktivace se ukládá v UTC, rozvrhy používají
  místní minuty dne a čtyři sezónní mapy. Chybějící pevný profil nemá náhradní cenu.
- `price_list.py`: textový PDF import s ověřením hlaviček, popisků, jednotek,
  pořadí rozvrhů, úplnosti a součtů. Nekonečné částky, nejasná struktura a
  chybějící buňky se odmítají před uložením.
- `config_flow.py`: náhled všech pásem a editovatelných poplatků; potvrzení
  samostatného profilu; výběr strategie, produktu a okamžiku aktivace.
  Budoucí plán nesmí jiná změna ceny nepozorovaně přepsat.
- `select.py`: okamžitá uživatelská volba strategie. Ověřuje existenci a
  účinnost profilu, uloží revizi a využije standardní reload config entry.
- `pricing.py` a `billing.py`: společná předpověď a živá cena. Dělí HDO,
  obchodní pásma a aktivace včetně sekundových hranic. Denní obnova nastane
  i při stejné ceně přes půlnoc. Původní srovnání bez dynamiky zůstává oddělené.
- `accounting.py`: samostatné stálé platby skutečné a srovnávacích variant,
  kompatibilní načtení starých součtů a explicitní mezery srovnávacího ocenění.
- `settlement_history.py` a `accounting_recovery.py`: historické cenové revize,
  denní platby a bezpečné vazby na starší účetní archiv. Původní archiv se nemaže.
- `sensor.py`, překlady a diagnostika: nové aktivní výstupy, zachování starých
  identifikátorů, zneznámění neplatných cen a redakce zdrojových názvů v diagnostice.
- `dashboard.py`, `dashboard_template.json` a `frontend/dashboard-generator.js`:
  společná prezentace obou strategií, převod registry ID včetně přejmenovaného
  voliče a zachování hlavního pohledu, detailů a editoru záloh.
- `scripts/build_release.py`: české release notes a sestavení z neměnného Git
  snapshotu. Zápis na GitHub není součástí lokálního sestavení.

Synchronní zachycení odečtu nemění řízení spotřebičů. Při restartu se obnoví
uložený rozpracovaný interval; unload uloží stav a zruší odběry a časovač.
Smluvní trial a dosavadní volba skutečného ocenění zůstávají oddělené od volby
strategie. Modelovaná úspora se nevydává za potvrzenou vratku ČEZ.

## Finální kontroly

| Kontrola | Výsledek |
| --- | --- |
| Jednotkové testy | 116 úspěšných |
| Lifecycle testy skutečného Home Assistantu | 105 úspěšných, HA 2025.1.4, odpovídající plugin 0.13.205 |
| JavaScript: dashboard a vydání | 28 úspěšných |
| Ruff: runtime, testy a skripty | Bez nálezů |
| Kompilace syntaxe Pythonu | Úspěšná |
| Kontrola whitespace změn | Bez nálezů |
| Import obou dodaných PDF | Čtyři mapy po 10/8/10/8 intervalech, všechny souhrny D57d souhlasí |
| Instalační ZIP | 39 souborů, kontrola integrity, manifest 1.1.0 a přesná shoda každého runtime souboru |
| Release notes | Pouze česká sekce 1.1.0; bez sekcí vydávání a vývojářských kontrol |

Cenové testy zahrnují období, svátky, 23/25hodinové dny, aktivaci uvnitř minuty,
nezměněný procentní profil, neplatné vstupy, restart přes aktivaci, neznámé HDO,
rozdílné stálé platby i roční odběr pevného importu. Ruční kontrolní ceny NT:
2,22394 Kč/kWh na dva roky, 2,32394 Kč/kWh na dobu neurčitou a 1,89894 Kč/kWh
pro původní standardní NT s −50 %. Stálé platby se k těmto cenám nepřičítají.

Lokální Python: 3.12.14. Windows asynchronní testy vyžadovaly loopback mimo
sandbox. Testovací backend zachoval HA policy a její executory, na Windows
použil selector pro korektní ukončení HTTP serveru; kontrola úniku úloh zůstala
aktivní. Linux CI se tím nemění. Běh na aktuální stabilní verzi HA a samotné
workflows HACS/Hassfest zde provedené nebyly; jejich úspěch se netvrdí.

Výsledky jsou dostupné v `tmp/unit-tests-1.1.log`, `tmp/ha-1.1.xml` a v
`dist/1.1.0/verification.json`. Tyto místní soubory nejsou součástí runtime ZIP.

## Balíček a stav vydání

- Instalátor: `dist/1.1.0/cez_dynamic_tariff.zip`.
- České poznámky: `dist/1.1.0/release-notes.md`.
- Kontrolní součet: `dist/1.1.0/cez_dynamic_tariff.zip.sha256`.
- Neměnný lokální snapshot: `5b0179cea2897b47105d033173ee408dde96f44a`.
- SHA-256 ZIP: `a1b729a68b32f460114c5c5b4e90f8eb2359c23f7bba12383e0ffe00de98f039`.

Neměnný snapshot vznikl v izolovaném místním repozitáři pouze pro sestavení.
Hlavní repozitář nebyl commitnut ani otagován; nic nebylo pushnuté nebo
publikované. Živý Home Assistant ani jeho uložené dashboardy se nezměnily.

## Praktické hranice a postup po aktualizaci

Podporovaný import je textová domácí dvoutarifní šablona ČEZ Prodej pro ČEZ
Distribuci, 21 % DPH, do 5 MB/6 stran; nové produkty mají čtyři cenové úrovně.
Sken nebo jiná struktura se odmítne. Budoucí pevný profil lze připravit,
standardní budoucí ceník se nadále importuje až od účinnosti.

Historické přepočty vyžadují správné smluvní účinnosti a pokrytí měření/HDO.
Konfigurace uložená před první aktivací není sama dokladem smlouvy v dávné
minulosti. Přírůstek měřidla se dělí rovnoměrně v rámci intervalu do 15 minut;
delší mezera není přesná rekonstrukce spotřeby. Skutečná historie domácnosti
zde nebyla analyzována a nebyly doporučené ani změněné provozní limity.

Po instalaci restartujte HA, obnovte prohlížeč, nahrajte PDF a samostatně
vyberte strategii, profil a začátek smlouvy. Ověřte dosavadní nastavení
skutečného ocenění versus simulace. Nové karty existujícího dashboardu převezměte
z náhledu generátoru. Podrobný postup a jednotky jsou v
[dokumentaci cenových režimů](dynamic-pricing-1.1.md).
