# Neznámé úspory: diagnostika a oprava issue #3

## Co je prokázáno

Při reprodukci nad kódem integrace před opravou vznikl stav `unknown` u úspor
i při úplném cenovém pokrytí. Výchozí hodnota elektroměru byla 17 000 kWh,
za pět minut následoval odečet 17 001 kWh. Obnovy cen rozdělovaly interval
na navazující úseky s hranicemi 0, 1, 61, 121, 181, 241 a 300 sekund.
Výpočet účtu před opravou sečetl jejich desetinné podíly jako čísla `float`;
součet vyšel nepatrně menší než 1. Do `unpriced_kwh` se proto připsalo
`1.1102230246251565e-16` kWh, ačkoli cena žádného úseku nechyběla.

Výpočet `comparison_complete` považuje jakoukoli nenulovou neoceněnou energii
nebo neúplné srovnání za překážku. Proto tento artefakt způsobil `unknown`
u `dynamic_savings`, `realized_savings` a `daily_savings`. Senzor
`unpriced_energy` přitom hodnotu zaokrouhluje na šest desetinných míst, takže
může zobrazit `0.0` i tehdy, když atribut `unpriced_energy_kwh` obsahuje malou
nenulovou hodnotu. Výše uvedené chování je doložené reprodukcí; skutečná
vstupní data konkrétní instalace popsané v issue nebyla k dispozici, a nelze
tedy tvrdit, že její problém má prokazatelně stejnou příčinu.

Opravené účetnictví sčítá délku skutečně oceněných úseků jako `timedelta`
s rozlišením mikrosekund. Teprve rozdíl proti celé délce intervalu převede
na podíl spotřeby v kWh. Žádná tolerance nepotlačuje malou skutečnou mezeru:
například při rovnoměrném odběru 1 kWh za 300 s zůstane chybějící 1 µs
neoceněná jako `1/300000000` kWh. Jednotky a výpočet oceněných nákladů se
nemění. Časové řádky se stejně jako před opravou předpokládají bez překryvu.

Úspory jsou modelové porovnání nákladů v Kč a mohou být i záporné; nejsou
potvrzenou vratkou ČEZ. Samostatná entita procentuální úspory zde není.
Procenta u `current_modifier` a souvisejících entit označují tarifní pásmo,
nikoli vypočtenou úsporu.

## Jak rozlišit běžné stavy

1. U některého senzoru úspor prohlédněte atributy `comparison_complete`,
   `unpriced_energy_kwh`, `comparison_unpriced_kwh`, `pricing_status`,
   `strategy_status` a `hdo_tariff`. Obě hodnoty neoceněné energie jsou
   kumulativní v kWh; `comparison_unpriced_kwh` znamená, že chyběla cena pro
   některou srovnávací variantu. Posuzujte celé atributy, ne jen zaokrouhlený
   stav `unpriced_energy`.
2. Ověřte konfiguraci elektroměru a jeho skutečné stavy, jednotku (`Wh`, `kWh`
   nebo `MWh`), návaznost odečtů a jejich čas. Stav `unknown`, `unavailable`,
   nečíselná, nekonečná, záporná hodnota nebo nepodporovaná jednotka nejsou
   platným odečtem. Nula naopak platným odečtem je.
3. Ověřte stav a platnost HDO, rozvrh a čas jeho poslední aktualizace, soulad
   živého VT/NT s rozvrhem, aktuální cenový profil a stav cenové strategie.
   Neúplná cena nebo srovnávací varianta musí zůstat neznámá. Při prodlevě
   mezi dvěma platnými odečty přes 15 minut se celý přírůstek uloží jako
   neoceněný, protože jeho časové rozložení není dostatečně známé.
4. Porovnejte období a dostupnost historie před rozhodnutím o obnovení dat.
   `comparison_complete` popisuje aktuální stav cenové strategie a dosud
   uložené účetní součty; samo o sobě nedokazuje nepřetržité měření ani úplnou
   historii. Po neplatném stavu elektroměru se výchozí odečet zruší a první
   další platná hodnota vytvoří nový základ. Spotřebu v této ztracené mezeře
   integrace ze samotných těchto stavů nezná a jako kvantifikovanou neoceněnou
   energii ji nezaznamená. Dosavadní součty a `comparison_complete` tedy mohou
   nadále vypadat úplné i přes tento výpadek.

Číselná nula úspory může znamenat dosud žádný zaúčtovaný přírůstek nebo
skutečnou nulovou úsporu v evidovaném období; sama nepotvrzuje úplné historické
pokrytí. `unknown` znamená, že pro danou hodnotu nejsou splněny její podmínky;
neznamená automaticky nulovou spotřebu ani chybu tohoto výpočtu. Hodnota
`unavailable` u entit koordinátoru odpovídá jeho nedostupnosti či neúspěšné
aktualizaci, zatímco `unknown` může být platným výsledkem výpočtu `None`.

Další legitimní důvody `unknown` závisí na konkrétní entitě:

- `effective_price` vyžaduje kladnou základní cenu; jde o původní jednoduchý
  výpočet, oddělený od úplného cenového profilu.
- Konce a začátky levného pásma, další změna a další modifier nemusí existovat
  v prohledávaném období nebo aktuálně nemusí být aktivní levné pásmo.
- Aktuální ceny mohou chybět při nedostupném HDO nebo neplatném profilu.
  Minimum, jeho začátek a další změna ceny nemají být odhadnuty při neúplné
  budoucí časové ose; další změna může chybět i při úplné ose beze změny.
  `allocated_price` navíc vyžaduje kladnou roční spotřebu a stálou cenu.
- Nákladové a úsporové entity vyžadují nastavený elektroměr; úspory navíc
  vyžadují úplné skutečné a srovnávací ocenění a platnou aktuální strategii.
  Denní úspory se řídí i kumulativní úplností, nejen dnešním intervalem.
- Účetní a výhledové entity mohou potřebovat dostupnou historii, ocenění,
  potvrzenou smlouvu, spotřební profil nebo podklady záloh a sdílení; konkrétní
  důvody uvádějí jejich stavové a diagnostické atributy. `accounting_price`
  závisí také na známém režimu smlouvy. Nejsou zaměnitelné s běžnými úsporami.

## Dříve uložený artefakt

Oprava brání vzniku popsaného artefaktu v nově účtovaných intervalech. Nemění
již uložené součty a neprovádí automatickou migraci ani mazání neoceněné
energie. Ze samotné uložené malé hodnoty nelze bezpečně rozlišit zaokrouhlovací
artefakt od skutečné krátké mezery: původní časové podklady nemusí být
k dispozici. Proto mohou úspory zůstat `unknown` i po instalaci opravy a
restartu či znovunačtení integrace.

Obnovení vyžaduje samostatné, kontrolované posouzení zachované historie odečtů,
cen a HDO a případný ověřený přepočet z dostatečných podkladů. Bez nich nelze
spolehlivě určit správnou hodnotu. Automatický epsilon, vynulování ani ruční
zásah do uložených součtů zde nejsou součástí opravy.

## Regresní ověření

- Jednotkové testy ověřují původní fragmentaci, skutečnou vnitřní mezeru
  1 µs včetně explicitně neznámé ceny, přechod místní půlnoci a zachování již
  uloženého malého neoceněného součtu po obnovení.
- Testy s Home Assistantem používají místní cenový profil a platný rozvrh HDO,
  nikoli externí běhové API ČEZ. Pro VT i NT provedou tři pětiminutové odečty,
  průběžné obnovy, skutečný callback časovače s intervalem koordinátoru 60 s,
  reload a oddělené odpojení/znovusestavení integrace z úložiště Store.
  Kontrolují číselné hodnoty všech tří senzorů úspor, jejich identitu,
  nulovou neoceněnou energii a správné ceny. Dále ověřují výpadek ceny HDO,
  neplatné elektroměry, platnou nulu a interval nad 15 minut.
- Odpojení a nové sestavení integrace testuje uložení a obnovení dat, ale není
  doslovným restartem procesu či celého operačního systému Home Assistantu.
  Automatizovaný test úplného restartu procesu a ověření konkrétní instalace
  tímto nejsou nahrazeny.
- Stejná HA regrese s původní metodou z revize `dd43a3a` selhala pro NT i VT na
  `dynamic_savings=unknown` a `unpriced_energy_kwh=1.1102230246251565e-16`.
  S opravenou metodou prošly všechny případy cílené sady. Jednotková regrese
  s originální metodou selhala na stejném nenulovém zbytku; skutečná mezera
  se neocenila v obou verzích.

Příkazy pro připravené prostředí závislostí:

```powershell
python -m unittest discover -s tests -p test_pricing.py -k issue_3 -v
python -m pytest tests_homeassistant/test_issue_3_savings.py --timeout=60 -q
```
