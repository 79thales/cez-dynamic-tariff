# Celková cena elektřiny a úspory

Úprava přidává volitelný výpočet do ČEZ Dynamic Tariff. Používá veřejné entity
nainstalované integrace [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce).
ČEZ HDO se nemění, nevyžaduje fork a nadále obstarává získávání signálu a jeho
rozvrhu. Původních 21 entit ČEZ Dynamic Tariff si zachovává ID, unique_id,
jednotky i význam. Zejména `effective_price` zůstává původním výpočtem obchodní
ceny ze stávajícího `base_price_kwh`.

## Profil tohoto odběrného místa

Podklad: dodaný ceník **Elektřina na 2 roky v akci, 30. 1. 2026**, D57d,
ČEZ Distribuce, potvrzený jistič **3×25 A**. Všechny zadané částky obsahují DPH.

| Složka | VT | NT | Jednotka |
|---|---:|---:|---|
| Dodávka | 3,18000 | 3,05000 | Kč/kWh |
| Distribuce | 0,91327 | 0,14097 | Kč/kWh |
| Daň z elektřiny | 0,03424 | 0,03424 | Kč/kWh |
| Systémové služby | 0,19873 | 0,19873 | Kč/kWh |
| Efektivní POZE | 0 | 0 | Kč/kWh |
| Dodavatel | 163,35 | | Kč/měsíc |
| Jistič 3×25 A | 671,55 | | Kč/měsíc |
| Nesíťová infrastruktura | 15,57 | | Kč/měsíc |

Stálé platby celkem: **850,47 Kč/měsíc**, tedy **10 205,64 Kč za 12 měsíců**.
Podle ceníku se POZE účtuje jako nižší výsledek podle jističe nebo spotřeby.
Platba podle jističe je nulová, proto se zde neúčtuje 598,95 Kč/MWh uvedených
ve druhé alternativě. Pro budoucí ceník s nenulovým limitem POZE je v této verzi
nutná ručně stanovená efektivní sazba a vyrovnání za zúčtovací období.

Součet zveřejněných složek dává bez Dynamického tarifu **4,32624 Kč/kWh VT**
a **3,42394 Kč/kWh NT**. Souhrnný řádek PDF uvádí ve VT 4,32625 Kč/kWh;
rozdíl 0,00001 Kč/kWh vzniká zaokrouhlením jednotlivých řádků ceníku.

| Dynamická změna obchodní ceny | Celková cena VT | Celková cena NT |
|---|---:|---:|
| −50 % | 2,73624 | 1,89894 |
| −10 % | 4,00824 | 3,11894 |
| 0 % / bez Dynamického tarifu | 4,32624 | 3,42394 |
| +10 % | 4,64424 | 3,72894 |
| +25 % | 5,12124 | 4,18644 |

Částky v tabulce jsou Kč/kWh včetně DPH, před rozpočítáním stálých plateb.
Procentní změna se používá **pouze na dodávku**, podle smluvních dynamických
pásem, která lze stále upravovat v původním nastavení.

## Nastavení

1. Po instalaci upravené integrace otevřít **Konfigurovat**.
2. V základním kroku zapnout **Nastavit celkovou cenu a úspory**. Původní
   základní cenu, prahy a rozvrhy zachovat, aby se chování původních entit nezměnilo.
3. Projít původní kroky prahů a rozvrhů. Pak se otevře cenový profil.
4. Zapnout nové cenové senzory a vybrat **Použít Dynamický tarif pro skutečnou cenu**.
   Vypnutí této volby přepne novou skutečnou cenu na běžný VT/NT. Obě varianty
   se vždy počítají souběžně pro srovnání.
   Volba **Zahrnout stálé platby do nákladů** rozhoduje, zda je připočítat
   k denním a celkovým nákladům. Ve výchozím nastavení je zapnutá.
5. Vybrat níže ověřené existující entity. Pokud je vhodná entita jediná,
   formulář ji nabídne. Při více signálech vybrat všechny tři HDO entity
   ze stejného zařízení a pro stejné odběrné místo jako elektroměr.
6. Potvrdit částky z ceníku v kroku **Složky ceny včetně DPH**.

| Účel | Ověřená entita |
|---|---|
| Stav nízkého tarifu EVV3 | `binary_sensor.cez_hdo_lowtariffactive_hdo_evv3` |
| Rozvrh EVV3 | `sensor.cez_hdo_schedule_hdo_evv3` |
| Platnost HDO dat EVV3 | `binary_sensor.cez_hdo_data_valid_hdo_evv3` |
| Kumulativní odběr GoodWe ze sítě | `sensor.66_technicka_mistnost_goodwe_meter_total_energy_import` |

Rozvrh této instalace má atribut `schedule` s intervaly `start`, `end`, `tariff`
a `last_update`. Adaptér pracuje s tímto skutečně ověřeným formátem, převádí
upstream konec 23:59:59 na půlnoc a respektuje šestidenní platnost dat.
Nepřebírá cenu z ČEZ HDO: v nynější konfiguraci jsou v jeho cenových entitách
hodnoty 3050/3180 označené jako Kč/kWh. Do nového výpočtu patří 3,05/3,18 Kč/kWh.
Žádné entity ani nastavení ČEZ HDO se kvůli tomu nepřepisují.

Změna hodnoty jističe nebo názvu sazby v tomto profilu sama nevyhledává jiné
distribuční ceny. Při změně odběrného místa nebo ceníku upravit také příslušné
ceny a stálé platby. Revize změněných cen je označena `custom`.

## Nové entity

Všechna následující ID začínají `sensor.cez_dynamic_tariff_`. Home Assistant
může při kolizi ID přidat suffix; původní registrované entity nikdy nepřejmenováváme.
Nové entity se přidají jen při zapnutí cenového profilu.

| Suffix | Význam |
|---|---|
| `daily_cost` | Dnešní změřený variabilní náklad plus podíl stálých plateb, pokud je zapnutý |
| `daily_fixed_cost` | Stálé platby / počet kalendářních dní aktuálního měsíce |
| `daily_savings` | Dosažená úspora při dnešní změřené spotřebě |
| `total_price` | Cena další odebrané kWh podle zvolené varianty, HDO a ceníku, včetně DPH |
| `price_without_dynamic` | Cena stejného VT/NT bez procentních změn |
| `price_with_dynamic` | Cena stejného VT/NT s procentními změnami |
| `monthly_fixed_cost` | Měsíční součet stálých plateb |
| `allocated_price` | Odhad ceny kWh včetně `12 × měsíční platby / roční odběr` |
| `price_forecast` | `complete` / `incomplete`, v atributu intervaly pro dnešek a zítřek |
| `minimum_price` | Nejnižší cena od nynějška do konce zítřka |
| `best_price_start` | Začátek nejlevnějšího intervalu; nynější čas, pokud už probíhá |
| `next_price_change` | Další změna celkové ceny, včetně změny HDO |
| `actual_cost` | Odhad variabilních nákladů na změřený odběr od začátku sledování |
| `total_cost` | Tento odhad plus stálé platby připadající na sledovaný čas, pokud je jejich zahrnutí zapnuté |
| `realized_savings` | Náklady bez dynamiky minus náklady podle zvolené skutečné varianty |
| `dynamic_savings` | Náklady bez dynamiky minus náklady s dynamikou, nezávisle na zvolené variantě |
| `potential_savings` | Teoretická další úspora při přesunu odběru do nejlevnějšího známého času |
| `unpriced_energy` | Přírůstky odběru, kterým nebylo možné přiřadit cenu |

Pro `allocated_price` je potřeba zadat **roční odběr ze sítě**. Spotřeba domu
včetně vlastní FVE se k rozpočítání plateb za nakupovanou elektřinu nehodí.
Například při 10 000 kWh ze sítě za rok připadají stálé platby na jednu kWh
částkou 1,020564 Kč. Výchozí odhad spotřeby je 0, tento senzor pak zůstává `unknown`.

## Význam úspor a přesnost

Denní stálý podíl se počítá podle kalendáře: v říjnu **850,47 / 31 = 27,434516 Kč**,
v měsíci s 30 dny **28,349 Kč**. Do `daily_cost` se započítá celá dnešní denní
částka a dosud změřený variabilní náklad. Při vypnuté volbě se denní cena skládá
jen ze změřeného odběru. Senzor `daily_fixed_cost` částku stále ukazuje pro kontrolu.
Denní senzory se obnoví při místní půlnoci; rozdělení přírůstku přes půlnoc
a změny letního času respektuje skutečně uplynulý čas. Souhrnný `total_cost`
zahrnuje stálé platby pouze za uplynulou sledovanou část dní, pokud je volba zapnutá.
Přepnutí této volby přepočítá celkový zobrazený odhad; nemění skutečně naměřený odběr
ani úsporu, protože stálé platby jsou pro obě srovnávané varianty stejné.

Cena další kWh (`total_price`) zůstává cenou proměnných složek. Stálé platby
nelze převést na Kč/kWh bez zvoleného odhadu odběru; k tomuto účelu slouží
samostatný `allocated_price`. Volba zahrnutí stálých plateb se týká `daily_cost`
a `total_cost`, ne původních entit ani cen za další kWh.

Dosažená úspora odpovídá srovnání **stejné skutečné spotřeby ve stejných časech**
s ceníkem bez dynamických procent. Může být záporná: odběr v drahých pásmech může
příplatek převážit. Při zvolené běžné ceně dosažená úspora nepřibývá, ale
srovnávací `dynamic_savings` nadále ukazuje výsledek hypotetické dynamické varianty.
Při přepnutí varianty se dosavadní historie zachová; výsledná dosažená úspora
pak zahrnuje období s oběma skutečně zvolenými variantami.

Teoretická další úspora není dosažená ani zaručená. Je horní odhad, který
předpokládá přesunutí veškerého změřeného odběru do nejlevnějšího času známého
při předchozím odečtu, do konce následujícího dne. Neověřuje výkon zařízení,
délku cyklu, komfort ani ztráty baterie. Je vhodná k rozhodnutí, které spotřebiče
má smysl dále analyzovat; není výsledkem optimalizace jejich skutečného provozu.

Odečty se počítají z přírůstků kumulativního importu (Wh, kWh nebo MWh), nikoliv
ze spotřeby domu nebo exportu. Při změně ceny uvnitř intervalu se přírůstek
rozpočítá podle času; skutečný profil spotřeby uvnitř intervalu neznáme.
Proto jde o odhad, jehož přesnost závisí na frekvenci a rozlišení elektroměru.
Interval delší než 15 minut se neocení, přírůstek přibude do `unpriced_energy`.
Reset elektroměru a nedostupný odečet zahájí nový výchozí odečet.

Součty přežijí reload a restart v lokálním úložišti Home Assistantu. První
odečet po zapnutí nebo restartu tvoří pouze výchozí stav. Historická spotřeba,
spotřeba během vypnutí HA a interval přes nedostupný odečet se zpětně neocení.
`unpriced_energy` nezahrnuje tyto nezměřitelné mezery; není dokladem úplnosti
celého zúčtovacího období. Stejně se stálé platby načítají jen za dobu sledování.
Při chybě HDO nebo neúplném výhledu se minimum a nejlepší čas nenabízejí jako
spolehlivá informace. Neznámé intervaly jsou ve výhledu `null`, nejsou domyšleny jako VT.

## Přehled a Energy dashboard

Samostatný nový pohled je připraven v `examples/full_price_dashboard.yaml`.
Stávající dashboard a jeho karty se neupravují. Rozvrh ceny je v atributu
`forecast` senzorů `total_price` a `price_forecast`; obsahuje ceny obou variant.

Přepočet senzorů běží s původním koordinátorem po 60 sekundách a při událostech
zdrojových entit. Home Assistant může rychle po sobě jdoucí aktualizace sloučit;
zobrazení proto nemusí změnit stav přesně na cenové hranici. Účtování přírůstků
využívá časové intervaly rozvrhu, takže známé hranice cen uvnitř odečtu rozděluje.

Na dodaném screenshotu je Energy dashboard nastaven na fixních 5,5 Kč/kWh.
Po nasazení lze u odběru ze sítě ručně vybrat **Použít entitu s aktuální cenou**
a nový `sensor.cez_dynamic_tariff_total_price`. Ten zahrnuje proměnné složky
včetně DPH. Stálé platby jsou samostatné, aby jejich výše nebyla násobena
okamžitým odběrem. Pro sledování celého odhadu lze místo toho použít nový
`total_cost`, který má třídu `monetary` a `state_class: total`. Obě metody
nedávat současně ke stejnému importu.

## Ověření

- Regrese všech původních rozvrhů a jejich veřejných entit.
- Částky D57d, POZE, omezení dynamického procenta na dodávku, stálé platby.
- Sloučení hranic HDO a dynamiky, půlnoc, chybějící data, platnost, DST.
- První odečet, přírůstky přes cenové hranice, restart, reset, záporné úspory.
- Skutečný testovací Home Assistant: nové entity, původní cena, obě varianty,
  zdrojové události, úložiště, reload, chyba HDO a čisté odpojení.

Rozšíření je součástí hlavního vydání 1.0.0. Původní nastavení se zachovává;
nový cenový profil je nutné zapnout a nastavit v možnostech integrace.
