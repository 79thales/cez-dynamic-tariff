# Vývoj, kontroly a vydávání

Tento dokument je určen správcům projektu a přispěvatelům. Uživatelský
popis, instalace a nastavení integrace jsou v [README](../README.md).

## Lokální kontroly

Testovací závislosti jsou uvedené v `requirements-test.txt`. Balíček `tzdata`
zajišťuje časová pásma také ve Windows; testy přechodu na letní a zimní čas
nesmějí chybějící časová data nahrazovat pevným posunem UTC.

```shell
python -m pip install -r requirements-test.txt
python -m compileall -q custom_components tests tests_homeassistant scripts
ruff check custom_components tests tests_homeassistant scripts
python -m unittest discover -s tests -v
node --test tests/test_dashboard_frontend.js tests/test_release_workflow.js
```

Testy skutečného životního cyklu Home Assistantu používají odpovídající dvojici
verzí `homeassistant` a `pytest-homeassistant-custom-component` podle
[workflow Quality](../.github/workflows/quality.yaml). Toto prostředí je
oddělené od rychlých jednotkových testů. Testy se spouštějí pro nejstarší
podporované prostředí, uvedenou novější verzi i aktuální stabilní vydání.
Workflow vypisuje pokrytí kódu; pro aktuální stabilní vydání hledá odpovídající
nezneplatněnou verzi testovacího pluginu. Chybějící dvojice kontrolu zastaví.

## Vydání nové verze

1. Uprav verzi v `custom_components/cez_dynamic_tariff/manifest.json` a přidej
   odpovídající sekci do `CHANGELOG.md`. Nové poznámky k vydání piš česky.
2. Ulož změny do Gitu a nech úspěšně projít **Quality**, **HACS** a **Hassfest**.
3. Odešli odpovídající tag `vX.Y.Z`. Workflow **Prepare release installer**
   sestaví instalátor z přesného commitu tagu, ověří verzi manifestu a přiloží
   `cez_dynamic_tariff.zip` k rozepsanému GitHub Release.
4. Zkontroluj poznámky, přiložený ZIP a výsledek workflow. Potom vydání zveřejni.
   Samotný tag nenahrazuje publikovaný GitHub Release s instalační přílohou.

Místní sestavení bez nahrání či zveřejnění:

```shell
python scripts/build_release.py --ref HEAD --expected-tag vX.Y.Z
```

Balíček obsahuje pouze soubory integrace z vybraného commitu; rozpracované
soubory se nezahrnují. Publikované tagy a instalační přílohy se nepřepisují.
Postup ověřování existujících balíčků popisuje [dokumentace skriptů](../scripts/README.md).

Odznaky stažení počítají instalační přílohu `cez_dynamic_tariff.zip`, nikoli
unikátní uživatele. Zdrojové archivy ani ukázky dashboardů počet nenavyšují.
Počty nevyžadují telemetrii v integraci a mohou se kvůli mezipaměti měnit se zpožděním.
