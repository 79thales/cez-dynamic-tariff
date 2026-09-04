# ČEZ Dynamic Tariff for Home Assistant

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2025.1%2B-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Integration-41BDF5?logo=home-assistant-community-store&logoColor=white)](https://hacs.xyz/)
[![Latest release](https://img.shields.io/github/v/release/79thales/cez-dynamic-tariff)](https://github.com/79thales/cez-dynamic-tariff/releases/latest)
[![HACS validation](https://github.com/79thales/cez-dynamic-tariff/actions/workflows/hacs.yaml/badge.svg)](https://github.com/79thales/cez-dynamic-tariff/actions/workflows/hacs.yaml)
[![Hassfest](https://github.com/79thales/cez-dynamic-tariff/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/79thales/cez-dynamic-tariff/actions/workflows/hassfest.yaml)
[![Quality](https://github.com/79thales/cez-dynamic-tariff/actions/workflows/quality.yaml/badge.svg)](https://github.com/79thales/cez-dynamic-tariff/actions/workflows/quality.yaml)

<p align="center">
  <img src="custom_components/cez_dynamic_tariff/brand/logo.png" alt="ČEZ Dynamic Tariff" width="180">
</p>

## English overview

ČEZ Dynamic Tariff is an independent custom integration for Home Assistant users of the ČEZ Dynamic Tariff product in the Czech Republic. It determines the current tariff period and percentage price modifier from a daily schedule, then exposes the result through sensors, binary sensors, and attributes suitable for Home Assistant dashboards and automations.

### Features

- 16 sensors for the current tariff period and modifier, season and day type, optional effective trading price, the next tariff change, the next cheap period, configurable thresholds, and tariff maps for today and tomorrow.
- 4 binary sensors indicating cheap, super cheap, expensive, and very expensive periods.
- Four bundled schedules covering April-September and October-March, each split into workdays and weekends or Czech public holidays.
- Editable schedule entries in `HH:MM=modifier` format, with support for adding or removing tariff periods and changing their percentage modifiers.
- Configurable classification thresholds used by tariff maps, binary sensors, and automations.
- Three optional example automation blueprints are included in the repository for controlling devices during cheap, super cheap, and expensive periods.

### Tariff data and pricing

The bundled schedules are transcribed from the official [ČEZ Dynamic Tariff product page](https://www.cez.cz/cs/nova-energetika/dynamicky-tarif) and the ČEZ document [Prices in ČEZ Dynamic Tariff time periods](https://www.cez.cz/webpublic/file/edee/2024/09/dynamickytarif_pasma.pdf). Their internal revision is `cez-public-table-2024-09`.

This is a schedule-based integration. It does **not** download current prices, contract data, or revised tariff schedules from the internet. Users can edit all four schedules in the integration options if their contract differs from the bundled data. ČEZ may change its product terms, so users should compare the bundled schedule with their current contract before relying on it for financially significant automations.

An optional base price can be used to calculate an effective price for the electricity trading component. Distribution charges, taxes, fixed fees, and other regulated components are not included.

### Requirements, installation, and configuration

Home Assistant `2025.1.0` or newer is required.

1. Install the repository through HACS. If it is not yet available in the default HACS catalog, add `https://github.com/79thales/cez-dynamic-tariff` as a custom repository of type **Integration**. Manual installation is also documented below.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and select **ČEZ Dynamic Tariff**.
4. Set a name, the optional base trading price, and whether Czech public holidays should use the weekend/holiday schedule.
5. Use **Configure** on the integration entry to edit thresholds and schedules or restore the bundled defaults.

[Open this repository in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=cez-dynamic-tariff&category=integration) · [Start the configuration flow](https://my.home-assistant.io/redirect/config_flow_start/?domain=cez_dynamic_tariff) · [Latest release](https://github.com/79thales/cez-dynamic-tariff/releases/latest)

## Česká dokumentace

Vlastní integrace pro Home Assistant, která vystavuje aktuální pásmo ČEZ Dynamického tarifu jako senzory a binární senzory. Výchozí rozvrh je součástí projektu a časová pásma i jejich změny ceny lze upravit přímo v možnostech integrace; integrace nestahuje aktuální ceny z internetu.

[Aktuální vydání](https://github.com/79thales/cez-dynamic-tariff/releases/latest)

## Požadavky

- Home Assistant `2025.1.0` nebo novější
- HACS (při instalaci přes HACS)
- připojení k internetu pouze při instalaci/aktualizaci závislosti `holidays`

## Co integrace umí

- vypočítá aktuální změnu ceny podle výchozího nebo vlastního rozpisu ČEZ
- vystaví aktuální tarifní pásmo, sezónu, typ dne a nejbližší další levné okno
- ukáže čas a hodnotu nejbližší skutečné změny tarifu
- připraví dynamickou mapu tarifu pro dnešek i zítřek
- vystaví pomocné entity:
  - práh levného pásma v %
  - práh super levného pásma v %
  - práh drahého pásma v %
  - práh velmi drahého pásma v %
  - informaci, zda je právě levné, super levné, drahé nebo velmi drahé pásmo
- umí zohlednit české státní svátky jako nepracovní dny
- umožňuje přidávat, odebírat a upravovat tarifní pásma včetně časů a procentních změn ceny

## Instalace do Home Assistantu

### Varianta 1: ruční instalace

Zkopíruj složku:

```text
custom_components/cez_dynamic_tariff
```

do konfigurační složky Home Assistantu:

```text
/config/custom_components/cez_dynamic_tariff
```

Pak restartuj Home Assistant.

Po restartu:

- otevři **Nastavení -> Zařízení a služby**
- klikni na **Přidat integraci**
- najdi **ČEZ Dynamic Tariff**

### Varianta 2: instalace přes HACS

[![Open your Home Assistant instance and open this repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=79thales&repository=cez-dynamic-tariff&category=integration)

Pokud repozitář ještě není ve výchozím katalogu HACS, přidej jej jako vlastní repozitář:

1. Otevři **HACS**.
2. Otevři nabídku **tři tečky**.
3. Vyber **Vlastní repozitáře**.
4. Vlož `https://github.com/79thales/cez-dynamic-tariff`.
5. Vyber typ **Integrace** a repozitář přidej.
6. Integraci nainstaluj a restartuj Home Assistant.
7. Otevři **Nastavení → Zařízení a služby → Přidat integraci**.
8. Vyhledej **ČEZ Dynamic Tariff**.

Po zařazení do výchozího katalogu HACS bude možné přeskočit krok s vlastním repozitářem.

[![Open your Home Assistant instance and start setting up this integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=cez_dynamic_tariff)
[![Open your Home Assistant instance and show your integrations.](https://my.home-assistant.io/badges/integrations.svg)](https://my.home-assistant.io/redirect/config/)

## Nastavení tarifních pásem

Otevři **Nastavení → Zařízení a služby → Integrace → ČEZ Dynamic Tariff → Konfigurovat**. Nastavení je rozdělené do tří kroků:

1. základní cena, zohlednění svátků a případná volba obnovení výchozích rozvrhů,
2. prahy super levného, levného, drahého a velmi drahého pásma,
3. čtyři samostatné denní rozvrhy.

Při obnovení výchozích rozvrhů se místo třetího kroku zobrazí samostatné potvrzení. Obnovení odstraní vlastní časy i procentní změny, ale zachová právě zadanou základní cenu, práci se svátky a prahy.

K dispozici jsou tyto rozvrhy:

- zimní pracovní den,
- zimní víkend nebo svátek,
- letní pracovní den,
- letní víkend nebo svátek.

### Zdroj a platnost výchozího rozvrhu

Vestavěná pásma odpovídají veřejné tabulce na stránce
[Dynamický tarif ČEZ](https://www.cez.cz/cs/nova-energetika/dynamicky-tarif)
a dokumentu [Ceny v časových pásmech Dynamického tarifu od ČEZ](https://www.cez.cz/webpublic/file/edee/2024/09/dynamickytarif_pasma.pdf).
Revize vestavěných dat je `cez-public-table-2024-09`; shoda všech čtyř rozvrhů
s tabulkou je chráněná regresním testem. ČEZ může podmínky produktu změnit, proto
je před použitím pro finančně významnou automatizaci vhodné porovnat rozvrh s
aktuální smlouvou. Vlastní smluvní pásma lze kdykoliv zadat v možnostech integrace.

Revize a zdroj jsou dostupné také v atributech `schedule_revision` a
`schedule_source_url` u aktuálního modifieru a obou map tarifu. Vlastní rozvrh
má revizi `custom` a zdroj je u něj prázdný, aby nebyl vydáván za tabulku ČEZ.

Každý rozvrh obsahuje položky ve formátu `HH:MM=změna_v_procentech`, oddělené čárkou. Například:

```text
00:00=-10, 03:00=-50, 05:00=+25, 08:00=+10
```

Tento příklad znamená:

- od `00:00` změnu ceny `-10 %`,
- od `03:00` změnu ceny `-50 %`,
- od `05:00` změnu ceny `+25 %`,
- od `08:00` změnu ceny `+10 %` až do půlnoci.

Pravidla rozvrhu:

- první položka musí začínat v `00:00`,
- časy musí být seřazené a nesmí se opakovat,
- změna ceny musí být celé číslo; znaménko `+` je volitelné,
- další čas automaticky ukončí předchozí pásmo,
- počet položek není pevný.

### Ověřené výchozí rozvrhy

**Říjen až březen – pracovní den**

```text
00:00=-10, 03:00=-50, 05:00=+25, 08:00=+10, 11:00=-10, 14:00=+10, 16:00=-10, 18:00=+25, 20:00=+10, 23:00=-10
```

**Říjen až březen – víkend nebo svátek**

```text
00:00=-10, 03:00=-50, 05:00=+10, 11:00=-10, 14:00=+10, 16:00=-10, 18:00=+10, 23:00=-10
```

**Duben až září – pracovní den**

```text
00:00=-10, 03:00=-50, 05:00=+25, 08:00=+10, 11:00=-50, 14:00=+10, 16:00=-10, 18:00=+25, 20:00=+10, 23:00=-10
```

**Duben až září – víkend nebo svátek**

```text
00:00=-10, 03:00=-50, 05:00=+10, 11:00=-50, 14:00=+10, 16:00=-10, 18:00=+10, 23:00=-10
```

Začátek intervalu je včetně a konec bez následujícího okamžiku. Zápis `03:00=-50, 05:00=+25` tedy znamená `-50 %` od `03:00:00` do `04:59:59…`; přesně v `05:00:00` začne `+25 %`. Poslední položka platí do půlnoci.

Pokud ČEZ zavede další pásmo, vlož do příslušného rozvrhu další položku, například `12:30=+5`. Pásmo odebereš odstraněním jeho položky. Volba **Obnovit výchozí rozvrhy z projektu** zahodí vlastní časy i procentní změny a načte výchozí hodnoty integrace.

Integrace změny sazebníku nestahuje automaticky. Nové oficiální pásmo proto můžeš ihned zadat ručně; výchozí rozvrhy projektu se následně upraví v nové verzi integrace.

Starší uložený formát obsahující jen časy je nadále podporovaný. Při otevření a uložení nastavení se automaticky převede na úplný formát s procentními změnami.

### Rozdíl mezi pásmem a prahem

- **Tarifní pásmo** je položka v denním rozvrhu. Určuje čas začátku a skutečnou procentní změnu ceny, například `12:30=+5`.
- **Práh** neurčuje čas ani cenu. Pouze zařadí skutečnou změnu do kategorie, nastaví barvu mapy a ovlivní příslušné binární senzory a automatizace.

Výchozí klasifikace:

| Kategorie | Výchozí rozsah | Zobrazení |
|---|---:|---|
| Super levné | `≤ -50 %` | 🟢 |
| Levné | `> -50 %` a `≤ -10 %` | 🟩 |
| Běžné | `> -10 %` a `< +10 %` | ▫️ |
| Drahé | `≥ +10 %` a `< +25 %` | ⬜ |
| Velmi drahé | `≥ +25 %` | ◻️ |

Hodnota `+25 %` je součástí výchozích rozvrhů pro pracovní dny od `05:00` a `18:00`. Výchozí víkendové/sváteční rozvrhy ji nepoužívají, ale lze ji do nich ručně přidat. Při `+25 %` jsou aktivní oba binární senzory: **drahé** i **velmi drahé**. Obdobně při `-50 %` jsou aktivní senzory **levné** i **super levné**.

Změna prahu nemění cenu ani časový rozvrh; mění pouze klasifikaci pásem pro senzory, barvy a automatizace.

## Vytvořené entity

Senzory:

- `sensor.cez_dynamic_tariff_current_modifier`
- `sensor.cez_dynamic_tariff_current_band`
- `sensor.cez_dynamic_tariff_cheap_threshold`
- `sensor.cez_dynamic_tariff_super_cheap_threshold`
- `sensor.cez_dynamic_tariff_expensive_threshold`
- `sensor.cez_dynamic_tariff_very_expensive_threshold`
- `sensor.cez_dynamic_tariff_season`
- `sensor.cez_dynamic_tariff_day_type`
- `sensor.cez_dynamic_tariff_effective_price`
- `sensor.cez_dynamic_tariff_next_cheap_start`
- `sensor.cez_dynamic_tariff_next_cheap_end`
- `sensor.cez_dynamic_tariff_next_cheap_modifier`
- `sensor.cez_dynamic_tariff_next_change`
- `sensor.cez_dynamic_tariff_next_modifier`
- `sensor.cez_dynamic_tariff_today_tariff_map`
- `sensor.cez_dynamic_tariff_tomorrow_tariff_map`

Binární senzory:

- `binary_sensor.cez_dynamic_tariff_cheap_now`
- `binary_sensor.cez_dynamic_tariff_super_cheap_now`
- `binary_sensor.cez_dynamic_tariff_expensive_now`
- `binary_sensor.cez_dynamic_tariff_very_expensive_now`

Integrace tedy vytváří celkem 20 vlastních entit: 16 senzorů a 4 binární senzory. Aktualizační entitu HACS vytváří HACS samostatně.

Všechny entity jsou při nové registraci přiřazené ke společnému zařízení **ČEZ Dynamic Tariff**. Integrace od verze `0.2.3` explicitně navrhuje výchozí ID podle stabilních interních klíčů uvedených výše, takže jejich suffix nezávisí na jazyku ani překladu názvu entity. Home Assistant zachovává dříve vytvořená nebo uživatelem změněná ID; ta lze přejmenovat v nastavení entity bez změny jejího `unique_id`.

Pokud se senzor ve verzi `0.2.2` nově zaregistroval jako `sensor.cez_dynamic_tariff_price_change`, přejmenuj jej jednou v nastavení entity na `sensor.cez_dynamic_tariff_current_modifier`. Dashboard i automatizace v tomto projektu používají stabilní ID `sensor.cez_dynamic_tariff_current_modifier`.

Stavy senzorů sezóny a typu dne zůstávají kvůli kompatibilitě české (`Letní`, `Zimní`, `Pracovní den`, `Víkend nebo Svátek`). Pro jazykově nezávislé automatizace používej jejich atributy `season_code` (`summer`/`winter`) a `day_type_code` (`workday`/`weekend_or_holiday`). Stejné kódy jsou dostupné také u obou map tarifu.

`next_change` ukazuje nejbližší budoucí okamžik, kdy se skutečně změní procentní modifier; hranice dvou sousedních pásem se stejnou hodnotou se přeskočí. `next_modifier` obsahuje hodnotu platnou od tohoto okamžiku. Naproti tomu trojice `next_cheap_start`, `next_cheap_end` a `next_cheap_modifier` hledá nejbližší budoucí okno na nebo pod nastaveným prahem levného pásma.

## Poznámky

- `base_price_kwh` je pouze obchodní složka ceny elektřiny
- distribuce, daně, měsíční fixní poplatky a regulované složky se do výpočtu nezapočítávají
- detekce svátků používá Python balíček `holidays`
- v nabídce integrace lze stáhnout diagnostiku obsahující nastavení a aktuálně vypočítaný stav; název konfigurace je v ní skrytý
- základní cena `0` znamená, že se efektivní cena nevypočítává
- všechny čtyři prahy `-50/-10/+10/+25 %` lze změnit v nastavení integrace
- časová pásma a jejich změny ceny lze změnit v **Nastavení → Zařízení a služby → Integrace → ČEZ Dynamic Tariff → Konfigurovat**
- zaškrtnutím **Obnovit výchozí rozvrhy z projektu** se vlastní časy i změny ceny zahodí

## Vydání nové verze

Verze integrace je uvedena v `custom_components/cez_dynamic_tariff/manifest.json`. Pro vydání nové verze:

1. Změň verzi v `manifest.json`.
2. Nech projít workflow HACS validation, Hassfest a Quality.
3. Vytvoř GitHub Release se stejnou verzí, například `vX.Y.Z`.

Pouhé vytvoření Git tagu bez GitHub Release nemusí HACS rozpoznat jako vydání.

## Vývoj a kontrola

Lokální kontrola syntaxe:

```bash
python -m compileall -q custom_components
```

Kontrola Ruff:

```bash
ruff check custom_components
```

Rychlé jednotkové testy bez instalace Home Assistantu:

```bash
python -m unittest discover -s tests -v
```

Skutečné lifecycle testy používají odpovídající dvojici verzí Home Assistantu a
`pytest-homeassistant-custom-component` ze CI workflow. Workflow je spouští pro
nejstarší deklarovanou verzi HA i aktuální stabilní vydání a vypisuje coverage.

Pull requesty a vydání automaticky kontrolují HACS, Hassfest a Ruff přes GitHub Actions.

## Blueprinty automatizací

Ve složce [`blueprints/automation/cez_dynamic_tariff`](blueprints/automation/cez_dynamic_tariff)
jsou připravené tři importovatelné blueprinty:

- řízení spotřebiče v levném pásmu,
- řízení nabíječky v super levném pásmu,
- vlastní akce při vstupu do drahého pásma a po jeho skončení.

Soubory lze zkopírovat do stejné cesty pod konfigurační složkou Home Assistantu
a následně z nich vytvořit automatizaci v **Nastavení → Automatizace a scény → Blueprinty**.

## Příklad automatizace v Home Assistantu

Tento příklad zapne bojler přes Shelly vždy, když je aktuální tarif na nebo pod nastaveným prahem levného pásma.

```yaml
automation:
  - alias: "Boiler zapnout v levném tarifu"
    mode: single
    triggers:
      - trigger: time_pattern
        minutes: "/5"
    conditions:
      - condition: template
        value_template: >
          {{
            states('sensor.cez_dynamic_tariff_current_modifier') | float(999) <=
            states('sensor.cez_dynamic_tariff_cheap_threshold') | float(-10)
          }}
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.bojler_nahore_1pm_switch_0
```

Příklad vypnutí po skončení levného pásma:

```yaml
automation:
  - alias: "Boiler vypnout po skončení levného tarifu"
    mode: single
    triggers:
      - trigger: time_pattern
        minutes: "/5"
    conditions:
      - condition: template
        value_template: >
          {{
            states('sensor.cez_dynamic_tariff_current_modifier') | float(999) >
            states('sensor.cez_dynamic_tariff_cheap_threshold') | float(-10)
          }}
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.bojler_nahore_1pm_switch_0
```

## Příklad Lovelace karty

Pokud chceš jednoduchou přehledovou kartu, vlož do ručně upravované karty tento YAML:

```yaml
type: entities
title: ČEZ Dynamic Tariff
entities:
  - entity: sensor.cez_dynamic_tariff_current_modifier
    name: Změna ceny o
  - entity: sensor.cez_dynamic_tariff_effective_price
    name: Aktuální cena
  - entity: sensor.cez_dynamic_tariff_current_band
    name: Aktuální pásmo
  - entity: sensor.cez_dynamic_tariff_day_type
    name: Typ dne
  - entity: sensor.cez_dynamic_tariff_season
    name: Sezóna
  - entity: sensor.cez_dynamic_tariff_next_change
    name: Další změna tarifu
  - entity: sensor.cez_dynamic_tariff_next_modifier
    name: Změna ceny po další změně
  - entity: sensor.cez_dynamic_tariff_next_cheap_start
    name: Další levné od
  - entity: sensor.cez_dynamic_tariff_next_cheap_end
    name: Další levné do
  - entity: sensor.cez_dynamic_tariff_next_cheap_modifier
    name: Další levný modifier
  - entity: sensor.cez_dynamic_tariff_cheap_threshold
    name: Práh levného pásma
  - entity: sensor.cez_dynamic_tariff_super_cheap_threshold
    name: Práh super levného pásma
  - entity: sensor.cez_dynamic_tariff_expensive_threshold
    name: Práh drahého pásma
  - entity: sensor.cez_dynamic_tariff_very_expensive_threshold
    name: Práh velmi drahého pásma
  - entity: binary_sensor.cez_dynamic_tariff_super_cheap_now
    name: Super levné pásmo právě teď
  - entity: binary_sensor.cez_dynamic_tariff_cheap_now
    name: Levné pásmo právě teď
  - entity: binary_sensor.cez_dynamic_tariff_expensive_now
    name: Drahé pásmo právě teď
  - entity: binary_sensor.cez_dynamic_tariff_very_expensive_now
    name: Velmi drahé pásmo právě teď
```

## Grafické mapy pásem v Lovelace

Integrace vystavuje dva senzory:

- `sensor.cez_dynamic_tariff_today_tariff_map`
- `sensor.cez_dynamic_tariff_tomorrow_tariff_map`

Oba mají v atributech připraveno:

- `display_map` pro přímé vložení do Markdown karty
- `schedule` jako seznam všech oken příslušného dne
- `legend` sestavenou ze všech procentních změn použitých v rozvrhu
- `season`, `season_code`, `day_type` a `day_type_code`

Mapa i legenda se automaticky přizpůsobí vlastním časům, změnám ceny a nově přidaným pásmům. Atribut `display_map` zůstává zachovaný pro zpětnou kompatibilitu a jednoduché Markdown karty:

```yaml
type: markdown
title: Dnešní mapa tarifu
content: |
  **{{ states('sensor.cez_dynamic_tariff_today_tariff_map') }}**

  {{ state_attr('sensor.cez_dynamic_tariff_today_tariff_map', 'display_map') }}

  {% for item in state_attr('sensor.cez_dynamic_tariff_today_tariff_map', 'legend') or [] %}
  `{{ item['token'] }} {{ item['modifier_percent'] }} %`
  {% endfor %}
```

Pro zítřek použij stejnou kartu s entitou `sensor.cez_dynamic_tariff_tomorrow_tariff_map`. Doporučený dashboard níže místo jednořádkového `display_map` prochází atribut `schedule`, takže zobrazí každé tarifní okno na samostatném řádku.

## Doporučený dashboard

Tento dashboard pro ČEZ Dynamic Tariff od verze v0.3.0 používá responzivní pohled **Sections**. Neobsahuje duplicitní karty pro mobil a počítač ani natvrdo zapsané časy či procenta. Dnešní a zítřejší mapu sestavuje z atributu `schedule`, takže se automaticky přizpůsobí vlastnímu rozvrhu, vlastním prahům i případnému novému pásmu. V dnešní mapě zvýrazní právě aktivní okno.

Hotová konfigurace celého dashboardu je v souboru [`examples/dashboard.yaml`](examples/dashboard.yaml). Je určena pro **Nastavení → Ovládací panely → editor nezpracované konfigurace**. Pokud se tvoje ID entit liší, vyber odpovídající entity ve vizuálním editoru.

Pro vložení pouze jednoho pohledu použij tuto část:

```yaml
title: ČEZ Dynamic Tariff
path: cez-dynamic-tariff
icon: mdi:transmission-tower
type: sections
max_columns: 3
dense_section_placement: true
sections:
  - type: grid
    cards:
      - type: heading
        heading: Aktuální tarif
        icon: mdi:transmission-tower

      - type: entities
        title: Právě teď
        state_color: true
        show_header_toggle: false
        entities:
          - entity: sensor.cez_dynamic_tariff_current_modifier
            name: Změna ceny
          - entity: sensor.cez_dynamic_tariff_effective_price
            name: Aktuální cena
          - entity: sensor.cez_dynamic_tariff_current_band
            name: Aktuální pásmo
          - entity: sensor.cez_dynamic_tariff_day_type
            name: Typ dne
          - entity: sensor.cez_dynamic_tariff_season
            name: Sezóna

      - type: markdown
        title: Stav tarifu
        content: |
          {% if is_state('binary_sensor.cez_dynamic_tariff_very_expensive_now', 'on') %}

          ## 🔴 Velmi drahé pásmo

          Preferovat provoz z baterie a omezit odběr ze sítě.

          {% elif is_state('binary_sensor.cez_dynamic_tariff_expensive_now', 'on') %}

          ## 🟠 Drahé pásmo

          Větší spotřebu je vhodné přesunout do levnějšího okna.

          {% elif is_state('binary_sensor.cez_dynamic_tariff_super_cheap_now', 'on') %}

          ## 🟢 Super levné pásmo

          Vhodná doba pro nabíjení baterie, ohřev bojlerů a nabíjení EV.

          {% elif is_state('binary_sensor.cez_dynamic_tariff_cheap_now', 'on') %}

          ## 🟩 Levné pásmo

          Vhodná doba pro vyšší spotřebu.

          {% else %}

          ## ⚪ Běžné pásmo

          Aktuální změna ceny: **{{ states('sensor.cez_dynamic_tariff_current_modifier') }} %**
          {% endif %}

  - type: grid
    cards:
      - type: heading
        heading: Další změny
        icon: mdi:clock-outline

      - type: entities
        title: Další změna tarifu
        show_header_toggle: false
        entities:
          - entity: sensor.cez_dynamic_tariff_next_change
            name: Změna nastane
          - entity: sensor.cez_dynamic_tariff_next_modifier
            name: Nová změna ceny

      - type: entities
        title: Další levné okno
        show_header_toggle: false
        entities:
          - entity: sensor.cez_dynamic_tariff_next_cheap_start
            name: Začátek
          - entity: sensor.cez_dynamic_tariff_next_cheap_end
            name: Konec
          - entity: sensor.cez_dynamic_tariff_next_cheap_modifier
            name: Změna ceny

  - type: grid
    cards:
      - type: heading
        heading: Nastavení pásem
        icon: mdi:tune-variant

      - type: entities
        title: Prahy
        show_header_toggle: false
        entities:
          - entity: sensor.cez_dynamic_tariff_super_cheap_threshold
            name: Super levné
          - entity: sensor.cez_dynamic_tariff_cheap_threshold
            name: Levné
          - entity: sensor.cez_dynamic_tariff_expensive_threshold
            name: Drahé
          - entity: sensor.cez_dynamic_tariff_very_expensive_threshold
            name: Velmi drahé

  - type: grid
    cards:
      - type: heading
        heading: Dnešní tarif
        icon: mdi:calendar-today

      - type: markdown
        title: Dnešní mapa
        content: |
          **{{ states('sensor.cez_dynamic_tariff_season') }} / {{ states('sensor.cez_dynamic_tariff_day_type') }}**

          {% set schedule = state_attr('sensor.cez_dynamic_tariff_today_tariff_map', 'schedule') or [] %}
          {% set current = states('sensor.cez_dynamic_tariff_current_band') %}

          {% for item in schedule %}
          {% set interval = item['start'] ~ '-' ~ item['end'] %}
          {% set mod = item['modifier_percent'] | int %}
          {% if interval == current %}
          ➡️ **{{ item['token'] }} {{ item['start'] }}–{{ item['end'] }} · {{ '+' if mod > 0 else '' }}{{ mod }} % · TEĎ**
          {% else %}
          {{ item['token'] }} **{{ item['start'] }}–{{ item['end'] }}** · `{{ '+' if mod > 0 else '' }}{{ mod }} %`
          {% endif %}
          {% endfor %}

  - type: grid
    cards:
      - type: heading
        heading: Zítřejší tarif
        icon: mdi:calendar-arrow-right

      - type: markdown
        title: Zítřejší mapa
        content: |
          **{{ state_attr('sensor.cez_dynamic_tariff_tomorrow_tariff_map', 'season') or '—' }} / {{ state_attr('sensor.cez_dynamic_tariff_tomorrow_tariff_map', 'day_type') or '—' }}**

          {% set schedule = state_attr('sensor.cez_dynamic_tariff_tomorrow_tariff_map', 'schedule') or [] %}

          {% for item in schedule %}
          {% set mod = item['modifier_percent'] | int %}
          {{ item['token'] }} **{{ item['start'] }}–{{ item['end'] }}** · `{{ '+' if mod > 0 else '' }}{{ mod }} %`
          {% endfor %}

cards: []
```
