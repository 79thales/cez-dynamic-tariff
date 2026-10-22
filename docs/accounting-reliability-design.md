# Trvalá odolnost účetnictví: audit a návrh

## Důkazy a hranice zjištění

Obnova z 12. října je hotová. Při zahájení implementace vracelo živé HA
`complete`, kontrolní bod 10. října a sedm bodů predikce. Nový místní snímek
je v ignorovaném `output/accounting-before-permanent-fix-2026-10-12.json`.
Žádné kontrolní hodnoty se při implementaci znovu nezapisují.

Historická chronologie je v accounting-reliability-task.md. Samotný běh
purge ani autora změny options nelze ze zachovaných stavů potvrdit.
Prokázaný problém kódu: SettlementHistory čte HDO pouze za 14 dní, nemá
trvalý archiv ocenění a při novém neúplném čtení zahodí předchozí výsledek.
I bez skutečného purge proto starší rozvrh vypadne z dotazu. Druhá
prokázaná cesta: history_auto po potvrzení bez samostatného souhlasu
nastavuje reference_date na prázdný řetězec. Není tím prokázáno, že právě
tato cesta způsobila změnu v 15:08.

## Datový model a priority

Vlastní verzovaný HA Store patří jedné config entry. Energie se ukládají
po uzavřených hodinách UTC, odděleně podle identity elektroměru. Ocenění
je navíc oddělené podle otisku cen, smluvního režimu, historických sazeb,
časového pásma a dynamických rozvrhů. Zálohy ani datum kontrolního bodu
nejsou součástí ceny jedné kWh. Jejich změna proto nesmaže historické
ocenění. Stálé platby se dopočítávají zvlášť podle kalendáře.

Priorita celkových částek: vyúčtovaná faktura pro celé období, výslovně
zadaný kontrolní bod včetně koncového dne, následné hodinové přírůstky.
Priorita přírůstku: kompatibilní peněžní statistika, výpočet z platných
historických cen a HDO, dříve ověřené ocenění shodné energie a revize.
Neznámý interval se nevymýšlí. Novější validní zdroj opravuje tentýž
klíč, nepřičítá další záznam. Neplatný nebo konfliktní vstup se odmítá
a diagnostikuje. Archiv se nepřenáší mezi různými elektroměry.

HDO archiv obsahuje ověřené rozvrhy s původním last_update, UTC hranicemi
a identitou zdroje. Dnešní rozvrh se neposouvá do minulosti. Identické
odpovědi jsou beze změny, rozdílné rozvrhy stejné revize jsou konflikt.
Data i kurzor backfillu se ukládají v jednom atomickém snapshotu. Retence
pokrývá nejméně celé účetní období a posledních 730 dní profilu.

## Životní cyklus a chyby

Běžný refresh a ruční backfill používají stejný zámek a archivační cestu.
Jediný úkol na instanci prochází minulost po sedmidenních blocích. Při
unloadu se zruší a uloží pozastavený stav; pokračování je výslovným
stiskem tlačítka. Opakovaný stisk při běhu se připojí k existujícímu běhu.
Po dokončení nový stisk znovu prověří zdroje. Timeout a přechodné chyby
mají omezené opakování; neočekávaná chyba se zaznamená s run_id.
Po změně konfigurace starý běh nesmí publikovat své výsledky.

Při poruše se zachovají ověřené historické intervaly. Případná předchozí
predikce zůstane pouze v atributu posledního úplného výsledku s datem
a příznakem zastarání; aktuální finanční senzory ji nevydávají jako novou.
Logují se změny důvodů a zotavení, nikoli každých pět minut stejná chyba.
Poškozený nebo nepodporovaný Store se nepřepíše prázdným archivem.

## Matice vstupů a odvozených hodnot

| Cesta / veličina | Vstupy a jednotky | Neúplnost / ochrana / ověření |
| --- | --- | --- |
| Recorder metadata | statistic_id, has_sum, Wh/kWh/MWh/CZK | Chybějící metadata a nesprávná jednotka mají vlastní důvod; peníze se nepoužijí jako energie. |
| Hodinové statistiky | UTC start/end, change v kWh nebo Kč | Deduplikace klíčů, konečné hodnoty, žádné záporné odběry, konflikty a pokrytí hodin včetně DST. |
| Dnešní statistiky a stavy | 5min change, kumulativní odečty, 15min maximální mezera | Dnes se nearchivuje jako uzavřený den; gap/reset/NaN nevytváří nulu. |
| Historické HDO | schedule, last_update, NT/VT | Ověřený archiv přežije retenci Recorderu; neplatné rozvrhy nejsou VT. |
| Živé HDO | stav, validita a stáří | Oddělený důvod od chybějící minulosti; po návratu nové čtení. |
| Ceníky a dynamická pásma | sazby Kč/kWh, Kč/měsíc, účinnost, smluvní režim | Otisk revize; chybějící profil nebo nepotvrzená smlouva nezíská smyšlené ocenění. PDF import již validuje vstupy před zápisem. |
| Denní energie/náklady/úspory | statistiky nebo měřený tail, kompatibilní finance | Samostatná úplnost energie, nákladů a baseline; žádné dvojí přičtení. |
| Období a finanční řady | kontrolní bod, hodinový archiv, sazby, kalendář | Základ včetně dne, novější přírůstky až od dalšího dne; souvislé pokrytí je podmínka úplnosti. |
| EDC příjmy | existující finanční statistic_id, CZK | Souhrn jednou, dnešní zpoždění explicitní; neznehodnotí samotnou energii. |
| Profil a predikce | úplné dny předchozích sezon, budoucí známý cenový model | Chybějící měsíce explicitní, budoucnost vždy odhad. Archiv oddělen od predikce. |
| Zálohy | měsíční klíč, Kč, paid_amount a původ | Existující validace duplicit a konečných částek; zpětné načtení nemění úhrady ani plán. |
| Options flow | jen skutečně odeslaná pole | Nesouvisející uložení zachová reference; vypnutí vyžaduje explicitní checkbox. Audit bez částek. |
| Entity/registry | entry_id + unique_id | Stabilní ID tlačítka/stavu, vazba na instanci, žádný odhad podle jména nebo přípony. |
| Dashboard a generátor | šablona, entity registry, aktuální místní pohledy | Jedno tlačítko/stav; migrace převzatého detailu je idempotentní a zachovává ostatní karty. |
| Store / backfill | vlastní verze, identita, kurzor a omezený přehled běhů | Atomický zápis, validace, restart, bez změn cizích statistik či HDO. |

## Ověření a nasazení

Implementace je připravena jako verze 1.0.9 v pracovní kopii. Verze se
zvyšuje také kvůli cache URL modulu Generate dashboard. GitHub release,
tag ani změna živého HA nebyly součástí této implementace. Aktuální
obnovené hodnoty, zálohy a cizí historie zůstaly beze zápisu.

Ověřeno na lokálním skutečném Home Assistantu 2025.1.4 s odpovídajícím
testovacím pluginem 0.13.205 a Pythonem 3.12. Windows testovací smyčka
potřebuje loopback TCP socketpair; testový conftest povoluje pouze jeho
konstrukci, ostatní zákaz síťových socketů a kontrola cíle zůstávají.
Vypnutí zdroje v testu je simulace, nikoli skutečný purge provozní DB.

Závěrečné místní kontroly: **102 unit testů, 89 HA testů a 22 testů
JavaScriptu prošlo**, stejně jako Ruff, kompilace Pythonu a kontrola
whitespace diffu. Testy zahrnují rovněž cache přes opakovanou hodinu DST,
kooperativní přecenění, oddělení sezonních energií od cen mimo období,
chybná EDC data a atomický zápis během zrušení úkolu.

Závěrečné pouze čtecí ověření živého HA 2026.10.1: účetnictví zůstalo
`complete`, neoceněná energie 0 kWh, sedm bodů finanční predikce.
Období, datum základu, platnost cen, měsíční zálohy, zdroj spotřeby,
smluvní režim a režim záloh odpovídaly snímku před vývojem. Nový místní
snímek je v ignorovaném
`output/accounting-after-permanent-fix-development-2026-10-12.json`.

Při budoucí změně cenového algoritmu je nutné zvýšit `algorithm` v otisku
revize, aby starý výpočet nebyl použit jako výsledek nové logiky. První
účetní Store má schéma 1; není přepisem ani migrací původního live ledgeru.
Budoucí změna schématu vyžaduje výslovnou migraci s regresním testem.

### Vztah akceptačních scénářů k ověření

| Scénáře zadání | Důkaz |
| --- | --- |
| A01–A02 | Unit archiv: opakování, překryv, konflikt; HA backfill dvakrát a opravený historický odběr. |
| A03–A04 | Jeden běh při dvojím stisku, společný zámek, pokračování od uloženého kurzoru a dokončení rozpracovaného zápisu při cancellation. |
| A05–A07 | Ocenění a predikce přežijí odstranění zdrojových HDO/energií a nový objekt nad uloženým archivem. Neznámé HDO zůstane neznámé; původní testy pokrývají živé HDO a neúplný dnešek. |
| A08–A10 | HA options zachování/explicitní vypnutí základu; změna konfigurace během await zablokuje zápis; revidovaná energie a cenová revize se nesčítají. |
| A11–A13 | Registry přejmenování s uchovanou vazbou, chybná metadata/jednotky, nula/NaN/konflikt, odlišné UTC hodiny DST a původní testy kontrolního bodu. |
| A14–A15 | Původní zálohy/EDC testy, nezávislé hrubé náklady při vadném EDC, reload a idempotentní přidání karty do převzatých detailů. |
| A16–A17 | Skutečná cesta HA Store s vloženou diskovou chybou, invalidní archiv je read-only, výpadek Recorderu zachová archiv a označí starší predikci. Cache po chybě ji nevydá jako nový úspěch. |

Některé scénáře tvoří více úzce zaměřených testů. Tato tabulka není
tvrzení, že byla nasimulována každá kombinace všech poruch. Timeout
má testované omezené opakování a zotavení bez minutového čekání;
síťové vzdálené API se v účetnictví
nepoužívá a zkoušení třikrát minutového zablokování lokální DB není
součástí rychlé sady. Nebyl nasimulován fyzický výpadek napájení disku.

### Postup provozního ověření a návratu

1. Před nasazením zazálohovat právě platné options a vlastní soubory
   `.storage/cez_dynamic_tariff.billing_<entry_id>` a případný nový
   `.storage/cez_dynamic_tariff.accounting_<entry_id>`. Zálohu finančních
   údajů držet místně. Zaznamenat období, kontrolní bod a plán/úhrady.
2. Nasadit celý adresář integrace včetně nových modulů, překladů,
   služeb a šablony podle aktuálního oprávnění uživatele. Reload/restart
   má zavést verzi 1.0.9; nejde o pokyn znovu obnovovat odečet.
3. Ověřit právě jedno tlačítko a stavový senzor podle unique_id vlastní
   entry, důvody a skutečné grafy. Použít náhled Generate dashboard;
   před případným uložením porovnat všechny místní pohledy a zálohy.
4. Spustit backfill; vyhodnotit skutečný výsledek a mezery. Druhý běh
   se stejnými zdroji musí zachovat součty. Rozsah může obsahovat dávno
   nedostupné hodiny pro profil, které nelze dotažením vymyslet.
5. Ověřit reload, přechod půlnoci a přirozenou retenci Recorderu.
   Nevyvolávat destruktivní purge kvůli testu. Přímý běh přes půlnoc
   a skutečné promazání v provozu zatím nebyly ověřeny.
6. Při návratu použít předchozí kód a původní options; nový vlastní
   účetní Store starší kód nečte. Soubor zachovat pro pozdější analýzu.
   Pokud byla nová data zpětně opravena, nepřepisovat je automaticky
   starším souborem. Cizí statistiky ani HDO se při návratu nemění.

Na živém HA 2026.10.1 nebyla nová verze spuštěna. Vyšší verze HA musí
ověřit projektová CI matice; místní testy starší verze ji nenahrazují.
Původ změny odečtu v 15:08 a samotný běh purge zůstávají neprokázané.
