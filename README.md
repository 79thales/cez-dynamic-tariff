# ČEZ Dynamic Tariff for Home Assistant

Custom Home Assistant integration that exposes the current ČEZ dynamic tariff window as sensors and binary sensors.

## What it does

- Calculates the current ČEZ dynamic tariff modifier from the published fixed schedule
- Exposes the current tariff band, season, day type, and the next cheap window
- Exposes helper entities:
  - cheap threshold (%)
  - super cheap threshold (%)
  - expensive now
- Supports Czech public holidays as off-days

## Repository structure

This repository is ready to:
- open directly in Visual Studio 2026 as a folder
- initialize as a Git repository
- push to GitHub
- install into Home Assistant manually
- install into Home Assistant through HACS custom repository after you publish it to GitHub

## Open in Visual Studio 2026

Use:
- **File -> Open -> Folder**
- select this repository root

Visual Studio can work with Python code directly from a folder, so you do not need a separate `.sln` or `.pyproj` file.

## Initialize Git

```bash
git init
git add .
git commit -m "Initial version of CEZ Dynamic Tariff integration"
```

If you want to publish to GitHub:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USER/cez-dynamic-tariff.git
git push -u origin main
```

## Before publishing to GitHub

Update these URLs in `custom_components/cez_dynamic_tariff/manifest.json`:

- `documentation`
- `issue_tracker`
- `codeowners`

and also adjust `hacs.json` if you want a different display name or minimum Home Assistant version.

## Install into Home Assistant

### Option 1: Manual install

Copy this folder:

```text
custom_components/cez_dynamic_tariff
```

into your Home Assistant config directory:

```text
/config/custom_components/cez_dynamic_tariff
```

Then restart Home Assistant.

After restart:
- go to **Settings -> Devices & services**
- click **Add integration**
- find **ČEZ Dynamic Tariff**

### Option 2: Install from Git repository with HACS

1. Publish this repository to GitHub
2. In Home Assistant open **HACS**
3. Open the **3 dots menu**
4. Select **Custom repositories**
5. Add your GitHub repository URL
6. Select type **Integration**
7. Add it
8. Find the repository in HACS and install it
9. Restart Home Assistant

## Entities created

Sensors:
- `sensor.cez_dynamic_tariff_current_modifier`
- `sensor.cez_dynamic_tariff_current_band`
- `sensor.cez_dynamic_tariff_cheap_threshold`
- `sensor.cez_dynamic_tariff_super_cheap_threshold`
- `sensor.cez_dynamic_tariff_season`
- `sensor.cez_dynamic_tariff_day_type`
- `sensor.cez_dynamic_tariff_effective_price`
- `sensor.cez_dynamic_tariff_next_cheap_start`
- `sensor.cez_dynamic_tariff_next_cheap_end`
- `sensor.cez_dynamic_tariff_next_cheap_modifier`

Binary sensors:
- `binary_sensor.cez_dynamic_tariff_expensive_now`

## Notes

- `base_price_kwh` is only the trading component of the electricity price
- distribution fees, taxes, fixed monthly fees, and regulated components are not included
- holiday detection uses the Python `holidays` package
