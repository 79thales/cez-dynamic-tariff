# Dva způsoby výpočtu dynamického tarifu (1.1.0)

Integrace uchovává standardní procentní profil a importované pevné profily
samostatně. Nejde o burzovní spot. Časové rozvrhy a částky vycházejí z ceníku
ČEZ; integrace sama nestahuje každodenní tržní ceny a neuzavírá smlouvu.

## Nastavení a aktivace

1. Zachovejte současný procentní profil. Aktualizace jej nepřepne na nový produkt.
2. Pro ocenění zapněte cenové senzory a nastavte platné entity HDO a odběru.
3. V nastavení integrace zvolte import ceníku PDF. Nové dynamické produkty
   podporují dobu neurčitou i smlouvu na 2 roky. Standardní import zůstává dostupný.
4. Náhled pevného ceníku zobrazí čtyři celé rozvrhy, obchodní ceny Kč/kWh včetně
   DPH, distribuční sazbu, jistič, zdroj, účinnosti a editovatelné poplatky.
   Uložení přidá samostatný profil. Standardní sazby ani aktivní režim nepřepíše.
5. V nabídce **Způsob výpočtu dynamického tarifu** vyberte procenta nebo pevné
   ceny a konkrétní nahraný produkt. Čas ponechte prázdný pro okamžité použití,
   nebo zadejte například `2028-04-08T00:00:00+02:00`.
6. Aktivace představuje skutečný začátek používání smluvní varianty. Datum
   vytištěné na PDF je účinnost dokumentu, nikoli potvrzení začátku vaší smlouvy.

Volič `select.cez_dynamic_tariff_tariff_mode` umožňuje okamžité přepnutí.
Pevný režim vyžaduje předem vybraný a již účinný profil. Volba v nastavení nebo
ve voliči nahrazuje dosud nenastalý plán. Při jiné změně cenového nastavení
nejprve zrušte plán okamžitou volbou a po změně jej nastavte znovu; integrace
jinak změnu odmítne, aby nezaměnila budoucí a současnou smlouvu. Import dalšího
nevybraného pevného profilu je povolený i při naplánované aktivaci.

Místní čas bez offsetu odmítáme: při přechodu zimního času může označovat dva
různé okamžiky. Uložená aktivace používá UTC a přežije restart. Rozvrhy se
vyhodnocují podle časového pásma HA; pro tuto instalaci používejte Europe/Prague.

## Výpočet a jednotky

Procentní obchodní cena = standardní dodávka VT/NT × (1 + procento / 100).
Pevná obchodní cena = přímá částka příslušného pásma. Procenta se na ni nepoužijí.
Celková cena kWh přičte distribuci dle HDO, daň, systémové služby, efektivní POZE
a případné další spotřební položky. Pevný profil používá vlastní regulované
položky a stálé platby; reference používá standardní profil.

Import převádí Kč/MWh na Kč/kWh dělením 1000. Částky už zahrnují DPH; ceny
v závorkách jsou bez DPH. Součty dodávky, distribuce, daně a systémových služeb
se ověřují proti osmi souhrnným řádkům dynamického ceníku. Kontrola dovoluje
zaokrouhlení do 0,05 Kč/MWh. POZE se řeší samostatně podle nižší příslušné sazby;
při odhadu podle ročního odběru zůstává označené jako odhad.

Kontrolní příklady z veřejných ceníků od 1. 6. 2026, D57d, včetně DPH:

| Varianta v nejlevnějším pásmu | Dodávka | Další spotřební složky NT | Celkem NT |
| --- | ---: | ---: | ---: |
| Pevný produkt na 2 roky | 1,85000 | 0,37394 | 2,22394 Kč/kWh |
| Pevný produkt na dobu neurčitou | 1,95000 | 0,37394 | 2,32394 Kč/kWh |
| Původní standardní NT 3,05 Kč/kWh s −50 % | 1,52500 | 0,37394 | 1,89894 Kč/kWh |

Další spotřební složky NT zde tvoří 0,14097 + 0,03424 + 0,19873 Kč/kWh.
Stejná pevná dodávka ve VT přičte 1,14624 Kč/kWh. Stálé platby nejsou v těchto
cenách kWh: 163,35 + 671,55 + 15,57 = 850,47 Kč/měsíc pro jistič 3×25 A.
To nejsou doporučení ke změně smlouvy ani odhady úspory konkrétní domácnosti.

## Semafory a návaznosti

🟢 nejlevnější, ⚪ levné, 🔘 neutrální, 🟠 drahé, 🔴 nejdražší.
Procentní režim používá dosavadní prahy. U podporovaných pevných ceníků se
čtyři úrovně určují ze všech čtyř rozvrhů společně; chybějící nejdražší pásmo
ve víkendovém dni proto nepřebarví drahé pásmo na červené.

Nové senzory se společným prefixem `sensor.cez_dynamic_tariff_`:

- `active_trade_price`: obchodní cena vybrané dynamické strategie v Kč/kWh.
- `active_price_level`: její cenová úroveň; při neznámé ceně/HDO je neznámá.
- `active_tariff_mode`: právě účinná strategie, `percentage` nebo `fixed_bands`.

Celková cena, předpověď a hledání nejlepšího intervalu používají společný
výpočet. Semafor označuje obchodní pásmo; minimum celkové ceny zohledňuje také
HDO. Předpověď obsahuje revize, přímé obchodní ceny a v pevném režimu
`modifier_percent: null`. Pevné smluvní rozvrhy vždy respektují české svátky;
původní volba jejich vypnutí platí pouze pro procentní profil. Původní procentní entity včetně binárních senzorů
zůstávají beze změny. Existující automatizace se automaticky nepřepojují.

Dosavadní volba `dynamic_pricing` nadále určuje skutečné ocenění proti
standardnímu základu. Není to druhý volič strategie: umožňuje zachovat model
na zkoušku a dosavadní účetní nastavení. Při vypnutí je skutečná cena standardní;
`price_with_dynamic` ukazuje vybranou dynamickou variantu pro porovnání.
Smluvní režim trial v účetnictví dál rozlišuje skutečnou fakturaci a simulaci.
Modelovaná úspora není potvrzená ani automaticky přiznaná vratka ČEZ.

Dashboard, Generate dashboard i přibalená šablona používají stejné cenové karty.
Generátor při převzetí místních pohledů aktualizuje známé cenové karty a přidá
jediný volič. Ostatní místní karty, hlavní pohled, detaily a zálohy zachová.
Uložený dashboard se aktualizací integrace sám nemění. Pokud pohled už existuje,
převezměte cenové karty z náhledu/exportu; generátor jej automaticky nepřepisuje.

## Historie, kvalita dat a omezení

Cenové události uchovávají předchozí i nové podklady a přesný okamžik aktivace.
Nový import nemění již zaúčtované hodnoty. U změny ceny se rozpracovaný odečet
rozdělí podle časové hranice; spotřeba uvnitř intervalu se nadále odhaduje jako
rovnoměrná. Přírůstek delší než 15 minut se neoceňuje odhadem. Neplatné měření,
reset a neznámé jednotky dodržují původní pravidla měřicího ledgeru.

Restart uchová rozpracovaný odečet, jeho původní ceny a poslední čas stálých
plateb. Při změně zdrojového elektroměru se jeho starý odečet nepoužije jako
základ nového měření. Starší instalace bez uloženého rozpracovaného odečtu
začne novým základem; spotřebu před prvním platným měřením nevymýšlí.

Archivovaná cena celé hodiny před aktivací zůstává dostupná i po ztrátě Recorder
historie. Hodina protínající aktivaci vyžaduje podklady pro rozdělení; při jejich
nedostatku se vykáže neúplné ocenění. Původní archiv se nemaže. Denní a historické
stálé platby respektují aktivace a skutečný počet sekund ve dnech změny času.
Srovnání zahrnuje rozdíly stálých plateb, pokud je jejich zahrnutí zapnuté.

Neplatný import nic neaktivuje. Nepodporovaná šablona, chybějící částky a
neshodné součty se odmítnou. Neznámá cena není nula. Neúplný výhled nepotvrdí
nejlevnější interval. Srovnávací úspora s mezerami v ocenění není úplný výsledek.

Podporovaný import: textové domácí ceníky ČEZ Prodej pro ČEZ Distribuci,
21 % DPH, dvoutarifní sazba, nejvýše 5 MB a 6 stran. Nové pevné produkty mají
čtyři cenové úrovně. Skeny, jiné šablony a jiné počty úrovní nejsou podporované.
Standardní import má nadále pouze jedno cenové období; budoucí standardní ceník
se importuje až od účinnosti. Pevný profil lze předem nahrát a aktivovat později.
Pro minulost před první uloženou změnou zůstává nutné správně nastavit smluvní
účinnost a historické profily; uložená předchozí konfigurace není doklad smlouvy.

Tato změna neřídí baterii, nabíjení ani bojlery a nemění výkonové limity.
Provozní doporučení nebo porovnání smluv podle skutečné spotřeby vyžaduje
samostatné ověření reprezentativní historie a jejího pokrytí.

## Ukládané podklady a časování pro údržbu

`fixed_price_profiles` obsahuje samostatné importy: identifikátor revize, produkt,
čtyři rozvrhy v minutách místního dne, částky včetně DPH, účinnosti, zdroj a jeho
SHA-256. Roční odběr v kWh zůstává součástí příslušného pevného importu pro POZE
a odhad rozpočítání stálých plateb. Standardní profil se tím nepřepíše.

`pricing_events` ukládá přesný UTC začátek, cenové podklady před/po změně a
kontrolní otisk. Při zachování identity měřidel připojí také vazbu na předchozí
účetní archiv. Vazba ověřuje energii, HDO, peněžní zdroj a časové pásmo; jiný
zdroj ji nepřevezme. Hodiny protínající aktivaci se přepočítají z dostupných dat.

Zdrojový odečet se zachytí bez čekání na obnovení dashboardu. Zobrazení při
běžných změnách respektuje původní slučování požadavků koordinátoru. Cenová
hranice, plánovaná aktivace a půlnoc mají samostatnou jednorázovou obnovu.
Při unloadu se odhlásí odběr stavů, zruší časovač a uloží rozpracovaný odečet
s jeho cenami. Restart z těchto podkladů pokračuje; po změně elektroměru se
nepoužije stará kumulativní hodnota. Zpětný skok hodin nevytváří stálou platbu
za záporný interval. Dlouhé nebo neplatné měření zůstává označené jako mezera.
