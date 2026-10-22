# Zadání: odolnost účetnictví, vysvětlení hodnot a dotažení dat

**Určeno k následné implementaci modelem Sol 6.1.** Tento dokument je
zadání; při jeho přípravě se neimplementuje ani nenasazuje trvalá oprava.
Ruční obnova dat popsaná níže je již dokončená samostatná část práce.
**Obnovu dat neopakovat.** Uživatel výslovně potvrdil, že oprava je již
na místě. Historické hodnoty níže jsou podklady pro audit a regresní testy,
nikoli pokyn k jejich opětovnému zápisu do Home Assistantu.

## Úvodní zadání pro Codex

Oprav integraci ČEZ Dynamic Tariff & Accounting tak, aby se neopakoval
výpadek finanční predikce z 12. 10. 2026. Nejdříve projdi minulost:
skutečné historické stavy, dlouhodobé statistiky, dostupné logy, zálohy,
změny nastavení, verze integrace a historii příslušného kódu. Dolož
chronologii od posledního funkčního výsledku po poruchu. Rozliš prokázané
příčiny, hypotézy a údaje, které už nelze ověřit. Potom implementuj
opatření, regresní testy, diagnostiku a tlačítko pro dotažení dat podle
tohoto dokumentu. Výsledkem má být funkční a ověřená oprava, ne pouze
návrh nebo opětovné ruční zadání původních hodnot.

Již provedenou obnovu dat zachovej. Před každou další změnou porovnej
aktuální stav s důkazy obnovy a vytvoř zálohu. Obnovu neopakuj,
nepřepisuj novější ruční úpravy a nepředpokládej, že snapshot z 12. října
je stále aktuální. Nejprve používej přímý HA konektor, potom podporované
REST/WebSocket API pro nepokryté operace; UI až pro zbytek. Přihlašovací
údaje nikdy nevypisuj ani neukládej do zadání nebo logů.

### Povinné prověření minulosti

- Rekonstruuj nejméně 10.–12. října včetně přechodů o půlnoci, výpadku
  ve 4:12 a odstranění data odečtu v 15:08. Rozšiř analýzu na celé
  zúčtovací období od 1. dubna a reprezentativní minulou zimu pro profil
  spotřeby. Kontroluj pokrytí, jednotky a časové pásmo každého zdroje.
- Porovnej uchovaná nastavení a průběhy options flow. Projdi všechna místa,
  která zapisují reference_*, včetně history_auto, _finish_options,
  reloadu a migrací. Je-li dostupná historie změn nebo kontext operace,
  použij ji. Samotný čas změny senzoru nedokazuje autora ani příčinu.
- Dolož skutečnou retenci Recorderu, konfiguraci automatického purge
  a dostupné důkazy jeho běhu. Odděl odstranění historie od omezeného
  dotazu, chyby parseru, neplatnosti HDO a chybně vyhodnoceného pokrytí.
- Porovnej verze a nasazení kódu před poruchou, po restartu a nyní,
  zejména čtení historických rozvrhů, prioritu zdrojů a uložení výsledků.
  Zkontroluj změny samotné integrace HDO a formátu jejího schedule.
- Vytvoř reprodukci z minimálních anonymizovaných historických vstupů.
  Reprodukce musí ukázat, proč byl stejný uzavřený den včera oceněný
  a dnes ztratil ocenění. Soukromé snapshoty nepřidávej do testovacích
  fixture veřejného repozitáře.
- Každou prokázanou příčinu spoj s konkrétní ochranou a testem. U příčin,
  které nelze zpětně určit, zaveď diagnostiku pro příští výskyt a uveď
  omezení důkazů. Netvrď, že všechny možné poruchy jsou vyloučené.

## Cíl a pořadí

Obnova funkční finanční predikce byla provedena 12. 10. 2026 a není
součástí zbývající práce. Následná implementace má zajistit, aby již úplně
spočtené období neztratilo ocenění jen kvůli zkrácení historie Recorderu,
restartu nebo přechodnému výpadku HDO. Rozsah tvoří prevence opakování,
backfill, kontroly existence a duplicit, diagnostika, logování a testy.
Nejdříve provést audit, potom implementovat a ověřit tato opatření.

## Ověřený incident a provedená obnova

Časy jsou v Europe/Prague, v tomto období UTC+02:00.

| Okamžik | Zjištěný stav |
| --- | --- |
| 11. 10. 2026 12:55 | Účetnictví complete, kontrolní odečet k 30. 9., sedm bodů finanční predikce, odhad přeplatku 2 667,36 Kč. |
| 12. 10. 2026 00:00–00:10 | Krátký přechod do incomplete a následné obnovení predikce. Prověřit návaznost výpočtu dneška a načtení historie. |
| 12. 10. 2026 04:12:23 | Predikce zmizela, neoceněný odběr 12,9 kWh. Datum kontrolního odečtu ještě existovalo. |
| 12. 10. 2026 15:08:27 | Datum kontrolního odečtu již prázdné; neoceněný odběr narostl na 488,69 kWh. |
| 12. 10. 2026 16:27 | Po obnově complete, neoceněný odběr 0 kWh, sedm bodů predikce. Odhad nákladů 29 575,79 Kč, přeplatek 2 424,21 Kč. |

Statistika elektroměru potvrdila odběr 12,9 kWh za 1. října a 0 kWh
za 2. října. Při kontrole začínaly zachované historické rozvrhy HDO
3. října. Živé HDO i platnost dat byly v kontrolovaném intervalu
03:30–05:00 dne 12. října dostupné. Ceník byl uložený; nastavená
platnost aktuálního ceníku byla 1. 11. 2025, začátek účetního období
1. 4. 2026. Tyto dvě hodnoty se nesmějí zaměňovat.

Promazání historie je podložená hypotéza, ne dosud ověřená událost purge.
Původ změny data odečtu v 15:08 zatím není doložen. V aktuálním seznamu
system_log/list nebyla při kontrole evidována chyba HDO; to nevylučuje
starší chybu před restartem. Neuzavírat incident pouhým zjištěním
aktuální dostupnosti senzoru.

Obnova použila poslední úplný den z uloženého stavu z 11. října:

- Datum kontrolního bodu: **10. 10. 2026**, včetně celého dne.
- Kumulovaný odběr od začátku období: **759,48 kWh**.
- Kumulované náklady včetně stálých plateb: **7 734,6990224903275 Kč**.
- Odběr byl odvozen jako 776,75 − 17,27 kWh; náklady převzaty
  z posledního uzavřeného denního bodu cost_actual_series.
- Jde o **obnovený výpočet HA**, nikoli nový odečet nebo fakturu ČEZ.
  Současný formulář používá společná pole reference_* a dashboard tento
  rozdíl neumí popsat: v trvalé opravě doplnit původ kontrolního bodu.
- Nová historie se přičítá až od 11. října, bez dvojího započtení základu.
- Původní kontrolní bod k 30. 9. měl 651 kWh a 7 165 Kč.
- Zaplacené zálohy 17 000 Kč a plán 32 000 Kč byly po obnově ověřeny.

Lokální důkazy obnovy jsou v souborech output/accounting-*.json,
které jsou vyloučené z Gitu:
accounting-before-recovery-2026-10-12.json,
accounting-recovery-checkpoint-2026-10-12.json a
accounting-after-recovery-2026-10-12.json. Zdrojový včerejší záznam:
C:/01.programovani/04.HA/proposals/goodwe-status-2026-10-11/states.json.
Tyto soubory obsahují místní údaje; nepřibalovat je do veřejného vydání.

## 1. Audit všech hodnot a jejich příčin

Audit zahrnuje **všechny metody, které odněkud načítají data**, nejen
výsledné senzory. Inventarizovat volání Recorderu, čtení stavů a atributů
HDO, načítání souborů a cache, import ceníku, vstupy EDC, registry,
REST/WebSocket akce a frontend. U každé metody uvést očekávaný formát,
validaci, chybové stavy, timeout, možnost opakování a dopad na ostatní
hodnoty. Ošetřit nedostupnost zdroje, chybná či částečná data, změnu
schématu, prázdnou odpověď, neplatné jednotky, selhání přístupu a zápisu,
výjimku i zrušení úkolu. Nezakrývat všechny chyby obecným except a
prázdným výsledkem. Chyba musí mít konkrétní příčinu a obnovovací cestu;
zachovat použitelné nezávislé hodnoty a poslední ověřená data.

Projít všechny entity integrace, atributy účetnictví, finanční i energetické
grafy a nastavení. Vytvořit matici: hodnota, jednotka, zdroj, vzorec,
časový rozsah, podmínky platnosti, možné příčiny unknown/unavailable,
obnovovací cesta a odpovídající test. Zahrnout současné ceny, cenové modely,
úspory, denní a kumulované energie a náklady, NT/VT, stálé platby, EDC,
profil spotřeby, zálohy, predikci a všechny datové řady grafů.

Prověřit zejména:

- Aktuální nedostupnost HDO oproti ztrátě historického rozvrhu; platnost,
  stáří, last_update, časové pokrytí, neplatný formát a krátké mezery.
- Recorder: skutečnou retenci a purge, vypnutý záznam, výjimky filtrů,
  krátkodobé a dlouhodobé statistiky, neúplné hodiny a chybějící metadata.
  U REST historie zadávat explicitní konec období, nevyhodnotit jednodenní
  odpověď jako historii celého požadovaného rozsahu.
- Správný elektroměr, reset kumulativního měření, záporné přírůstky,
  převody Wh/kWh/MWh a shodu zdroje již vypočtených peněžních statistik.
- Platnost smluvního ceníku a historických sazeb, import PDF, NT/VT,
  DPH, dynamická pásma, svátky, sezonu, finální a zkušební smluvní režim.
- Dnešek proti uzavřeným dnům, cache pěti minut, půlnoc, restart, reload,
  výpadek HA, časové pásmo a přechody letního času.
- EDC: jednotku CZK, zpoždění, skutečné časové přiřazení, chybějící dnešek,
  odečítání příjmů a případné dvojí započtení přes Energy.
- Nezadanou versus nulovou zálohu, částečné úhrady, automatické potvrzení,
  změnu režimu, souběh formulářů a zachování již potvrzených plateb.
- Referenční odečet: změnu období, skrytá/vynechaná pole, prázdný vstup,
  nabídku history_auto, migrace, reload a souběžné ukládání options.
  Doložit, které cesty mohou vymazat reference_date a za jakých podmínek.
- Frontend: správné entity_id, prázdná řada, null body, omezení časové osy,
  validace ApexCharts, načítání zdrojů a chování bez finanční predikce.

## 2. Uchování ověřených podkladů a výsledků

Navrhnout a implementovat trvalé uložení ověřeného ocenění uzavřených
intervalů nebo dnů a potřebných historických HDO podkladů. U každého
záznamu uchovat časové hranice, energii, peněžní složky, pokrytí a původ.
Zvolit a zdokumentovat prioritu faktury/ručního odečtu, obnoveného
kontrolního bodu, existujících shodných finančních statistik a dopočtu.

Cache musí být navázaná na elektroměr, období, smluvní režim a cenové
vstupy. Změna zdroje nebo sazeb nesmí potichu použít neslučitelné výsledky.
Oddělit uložené skutečné náklady od proměnlivé budoucí predikce. Zachovat
ověřené výsledky po purge a restartu; neúplný nový výpočet nesmí přepsat
úplný archiv prázdnem. Starší predikci lze ukázat pouze jako zastaralou
s časem výpočtu a důvodem, nikoli jako aktuální potvrzený výsledek.

Zajistit verzované úložiště, validaci, atomický zápis, migraci a bezpečnou
obnovu. Poškozená cache vyvolá konkrétní diagnostiku. Chybějící hodnoty
nejsou nula. Historické HDO nelze nahradit dnešním rozvrhem bez důkazu;
odhad musí zůstat oddělený od skutečného účetnictví. Původní odečet a jeho
původ zachovat při běžném uložení nesouvisejících nastavení. Výslovné
vypnutí odečtu srozumitelně popsat a zaznamenat změnu.

### Kontroly existence, identity a duplicit

Před čtením a před zápisem kontrolovat skutečnou existenci a identitu
zdroje i cíle. Pouhé podobné jméno, friendly_name nebo automaticky
vytvořená přípona entity není důkaz správné identity.

| Oblast | Povinná kontrola a chování |
| --- | --- |
| Config entry a zařízení | Ověřit entry_id, načtený runtime a vazbu zařízení. Pokud je více kandidátů, nedohadovat výběr. Oddělit data různých instancí. |
| Entity a registry | Rozlišit neexistující, zakázanou, přejmenovanou, dočasně nedostupnou entitu a chybějící atribut. Zachovat existující unique_id a uživatelská entity_id. Nové tlačítko i diagnostické entity se při reloadu nesmějí zdvojit. |
| Statistiky | Ověřit statistic_id, zdroj, jednotku, has_sum a význam state/sum/change. Nekopírovat již existující statistiku pod nové ID jen kvůli backfillu. Přejmenování entity nesmí vybrat jiný elektroměr. |
| HDO a cenové intervaly | Normalizovat hranice na jednoznačný čas UTC. Identické intervaly deduplikovat; překryv různých verzí řešit zdokumentovanou prioritou platných podkladů. Konflikt nesmí být skrytý pořadím načtení. |
| Historický archiv | Definovat stabilní klíč záznamu zahrnující instanci, zdroj, interval a druh veličiny. Revizi/původ vést tak, aby dvě verze téhož intervalu nebyly dvěma účtovanými odběry. |
| Opravená zdrojová data | Shodný vstup je no-op. Pozdější oprava nahrazuje příslušný výsledek podle jasných pravidel; nepřičítá se jako další energie či platba. Neúplná odpověď nesmí smazat úplný záznam. |
| Zálohy a EDC | Měsíc/platbu či interval příjmu započítat jednou. Nezdvojit roční a měsíční plán, potvrzenou platbu, souhrn EDC s jeho jednotlivými příjemci ani odečet příjmu přes Energy. |
| Kontrolní bod | Jednoznačně rozdělit období na základ včetně jeho koncového dne a novější přírůstky. Překrývající statistiky a základ nesčítat. Uchovat původ a složky částky kvůli přepnutí stálých plateb či sdílení. |
| Dashboard | Ověřit existenci vlastních pohledů, karet a zdrojů podle stabilní identity. Opakovaný náhled/generování nesmí přidat druhé tlačítko, kartu, zdroj ani subview. Respektovat místní složení. |

Existující podezřelé duplicity nejdříve vykázat s důvodem a vazbami.
Automaticky nemaž uživatelské entity, statistiky nebo pohledy. Sloučení
je přípustné jen při doložené shodě identity a významu, se zálohou a
ověřením návazností. Backfill opravuje vlastní data integrace; nepřepisuje
cizí dlouhodobé statistiky. Případnou potřebu importu vlastních statistik
nejprve zdůvodnit a otestovat idempotentní upsert podporovaným HA API.

Při opakování, překryvu bloků, souběhu a pokračování po pádu musí být
výsledné součty stejné jako při jediném úplném běhu nad stejnými vstupy.
Kurzor posouvat až po úspěšném uložení výsledku bloku. Pád mezi uložením
dat a kurzoru vyřešit opakováním bez duplicit; nikdy přeskočením dat.
Při opravě dřívějšího intervalu přepočítat závislé kumulované součty.

## 3. Diagnostika a logování

Zavést konkrétní kódy příčin, například live_hdo_unavailable,
historical_hdo_missing, energy_history_gap, cost_source_mismatch,
price_profile_missing, reference_disabled, advances_missing,
shared_income_pending a recorder_unavailable. Neomezit se na incomplete.

Pro každou nedostupnou odvozenou hodnotu uvést závislost, dotčené období,
pokrytí a objem neoceněné energie. Zobrazit čas posledního úspěšného čtení,
výpočtu a posledního úplného výsledku. Rozlišit úplnost jednotlivých
hodnot: výpadek EDC nebo úspory nesmí zneplatnit nesouvisející energii.

Logovat začátek, výsledek a chybu obnovy i změny důležitých nastavení,
včetně původu operace, revize a přechodu z úplného výsledku na neúplný.
Stejnou opakovanou chybu nezahlcovat každých pět minut; zaznamenat změnu
stavu a následné zotavení. Běžné logy nesmějí obsahovat tokeny ani celé
osobní finanční záznamy. Rozšířenou diagnostiku redigovat a zdokumentovat.

Každý běh backfillu musí mít identifikátor a logy se společným kontextem:
entry_id, typ zdroje, rozsah bloku, revize vstupů, fáze, doba běhu,
počet načtených/nových/opravených/shodných/odmítnutých záznamů, pokrytí
a kód příčiny. Volitelné podrobnosti patří do DEBUG. INFO použít pro
zahájení, ukončení a zotavení, WARNING pro neúplnost vyžadující pozornost
a ERROR pro selhání. Jednotlivé chyby nesmějí uniknout bez kontextu ani
vytvářet tisíce stejných hlášek. Uchovat omezený přehled posledních běhů
také po restartu, s definovanou retencí a limitem velikosti.

Chyby přístupu a neplatné konfigurace neopakovat rychlou nekonečnou
smyčkou. Přechodné síťové a časové chyby opakovat omezeně se zvětšujícím
se odstupem; respektovat omezení zdrojového API. Chybný záznam popsat
a izolovat, ale celý výsledek pak nesmí být označený za úplný. Zrušení
úkolu při unloadu odlišit od poruchy a bezpečně dokončit pouze rozpracovaný
atomický zápis. Neošetřenou výjimku neproměňovat na nulovou spotřebu.

## 4. Tlačítko „Dotáhnout a přepočítat data“

### Vzor existujícího řešení EDC

Před implementací prostudovat aktuální projekt
`C:/01.programovani/EDC Sharing stats`, zejména:

- `custom_components/edc_sharing/button.py`: EdcHistoryBackfillButton
  a jeho async_press.
- `custom_components/edc_sharing/coordinator.py`: async_initialize,
  async_start_history_backfill, _async_backfill_history,
  _async_save_history_backfill_state a dokončení/selhání úkolu.
- Navazující stavové senzory, překlady, dokumentaci a regresní testy
  backfillu; dohledat je v aktuální verzi projektu.

V přečtené verzi EDC existuje samostatný úkol na pozadí, ochrana před
druhým souběžným během, zpětné procházení historie po blocích, uložený
kurzor a počty zpracovaných bloků/dnů/hodin. Stav a chyba se ukládají,
další spuštění umí pokračovat z uloženého místa. Použít tento princip
pro ČEZ, nikoli bez rozmyslu kopírovat roční rozsah, EDC API nebo pravidla
importu statistik. Rozsah ČEZ vychází ze zúčtovacího období a potřeb
historického profilu. Projekt EDC je reference; tato práce jej nemění.

### Požadované provedení backfillu

Přidat nativní button entitu a odpovídající akci pro konkrétní config entry.
Vyložit dotažení jako nové načtení dostupných zdrojů a bezpečný dopočet
historie, nikoli pouhé obnovení stránky nebo vynulování účetnictví.

- Backfill má skutečně projít dostupnou minulost po omezených blocích,
  vyhledat mezery a pokusit se je doplnit z podporovaných zdrojů a
  ověřeného archivu. Ukládat kurzor, průběh, úspěšné bloky, zbývající
  mezery a chyby; umožnit pokračování po přerušení/restartu. Výslovně
  definovat, zda pokračování po restartu proběhne samo nebo tlačítkem.
  Nedostupný blok nesmí vynulovat úspěšné bloky; rozlišit neobnovitelnou
  mezeru, přechodnou chybu a datum mimo dostupný rozsah zdroje.
- Ruční akce obejde běžnou pětiminutovou cache a načte relevantní
  statistiky, zachované HDO podklady, cenové podklady a zvolený EDC zdroj.
  Pokud je potřeba obnovit zdrojovou integraci, použít jen její podporované
  rozhraní. Neměnit její konfiguraci a neslibovat stažení smazaných údajů.
- Průběh: čeká / běží / dokončeno / neúplné / chyba; zobrazit čas,
  co bylo doplněno a co stále chybí. Úspěch nehlásit jen podle přijetí akce.
- Jeden běh na config entry; opakované kliknutí spojit s běžícím úkolem.
  Vyřešit souběh pravidelné obnovy, změn options a unload/restartu.
  Při změně revize nevydat výsledek vypočtený podle starého nastavení.
- Dlouhé čtení provozovat v odpovídajícím executor vlákně, bez blokování
  HA. Definovat timeout, ukončení, omezené opakování přechodných chyb
  a zachování posledních ověřených dat při neúspěchu.
- Akce nesmí přepisovat zálohy, měnit odečty, resetovat měřidla,
  vytvářet duplicitní statistiky ani zdvojovat peníze nebo energii.
- Tlačítko a srozumitelný stav zařadit do existujícího detailního pohledu.
  Ve stejné změně aktualizovat dashboard_template.json i Generate dashboard,
  včetně převzetí již existujícího místního složení. Zachovat hlavní pohled,
  detailní subviews a editor záloh; ověřit uložený YAML a komentáře.

### Smlouva chování tlačítka a výsledku

Výchozí stisk obnoví data aktuálního zúčtovacího období a podklady
potřebné pro sezonní profil. Akce může nabídnout omezený explicitní
rozsah pro cílenou opravu; validovat začátek, konec a maximální rozsah.
Opakovaný stisk po dokončení znovu zkontroluje dostupné opravy zdrojů;
nejde o jednorázové tlačítko fungující pouze po instalaci.

Na kartě musí být vidět fáze, zpracované/celkové bloky, aktuální rozsah,
čas posledního úspěchu a srozumitelný výsledek. „Dokončeno“ znamená,
že byl požadovaný rozsah zpracován a ověřen; pokud v něm zůstaly mezery,
výsledek musí být „Neúplné“ s jejich rozsahem a příčinou. Nabídnout
pokračování po přerušení. Automatické opakování a ruční stisk používají
stejný mechanismus a kontrolu souběhu. Tlačítko se zpřístupní až při
dostupném runtime; chybějící potřebná konfigurace zobrazí konkrétní důvod.

## 5. Testy, dokumentace a přijetí

Přidat regresní scénář: úplné ocenění a predikce → odstranění starých
záznamů HDO → obnovení integrace. Ověřené uzavřené období musí zůstat
oceněné. Zároveň otestovat případ, kdy ocenění nikdy známé nebylo;
integrace je nesmí vymyslet. Samostatně testovat živý výpadek HDO a návrat.

Pokrýt změnu a zachování kontrolního bodu, identitu elektroměru, změnu
sazeb, poškození a migraci úložiště, DST, půlnoc, restart, vypnutý Recorder,
neúplné hodiny, nulovou spotřebu, zálohy a opožděné EDC. Testovat
opakované kliknutí, souběh a timeout tlačítka, částečný neúspěch a úspěšné
zotavení bez duplicitních součtů. Prověřit všechny příčiny z auditní matice.

Komentáře, description, české názvy a dokumentace musí vysvětlit účel,
vstupy, jednotky, podmínky, časování, souběh, restart a chování při chybě.
Opravit také označení původu kontrolního bodu v dashboardu: obnovený
výpočet HA nesmí být označený jako nový odečet ČEZ.

Před nasazením zazálohovat nastavení a vlastní úložiště integrace.
Po nasazení ověřit API i skutečný graf a finanční součty, původ údajů,
zachování záloh a všech pohledů. Dlouhodobé přijetí vyžaduje ověření přes
půlnoc a skutečné promazání historie; jediný okamžitý úspěch nestačí.
Výstupem bude auditní matice, popis prokázaných příčin a zbývajících
hypotéz, implementace, testy, dokumentace a protokol ověření v HA.

### Minimální akceptační scénáře

| ID | Scénář | Požadovaný výsledek |
| --- | --- | --- |
| A01 | Stejný backfill dvakrát | Stejné energie, peníze a počty unikátních záznamů; druhý běh nevytvoří duplikáty. |
| A02 | Překrývající se bloky a dvakrát stejná odpověď | Každý interval započten jednou, duplicity vykázány v diagnostice. |
| A03 | Dvojí stisk při pravidelné aktualizaci | Jediný backfill, bez závodu zápisů a bez ztráty novějších dat. |
| A04 | Restart mezi zápisem bloku a kurzoru | Bezpečné pokračování; nic nechybí a nic se nepřičte dvakrát. |
| A05 | Purge HDO a restart po úplném ocenění | Uzavřené ověřené náklady a základ predikce přežijí. |
| A06 | Historický den nikdy neměl HDO ani ověřené ocenění | Konkrétní mezera, ne smyšlená cena nebo nulový náklad. |
| A07 | Výpadek živého HDO nebo Recorderu a návrat | Rozlišená příčina, zachovaný archiv, automatické zotavení a log zotavení. |
| A08 | Uložení záloh/ceníku a zrušení formuláře | Původní kontrolní odečet zachován; pouze jeho výslovná změna se projeví a zapíše do auditu. |
| A09 | Změna zdroje, období nebo cen během backfillu | Stará revize se nezapíše přes novou; neslučitelné hodnoty se nepoužijí. |
| A10 | Opravený historický záznam ze zdroje | Nahrazení příslušného intervalu a přepočet závislostí, bez zdvojení. |
| A11 | Chybějící, přejmenovaná nebo zakázaná entita | Konkrétní diagnostika; žádné založení náhradního duplicitního elektroměru. |
| A12 | Nulové hodnoty, NaN, neplatné jednotky a poškozená odpověď | Nula zachována jen jako platná hodnota, neplatná data odmítnuta s příčinou. |
| A13 | DST a hranice kontrolního bodu | Žádná zdvojená/vynechaná hodina; správná délka dne a návaznost základu. |
| A14 | EDC zpoždění, změna úhrady a opakované potvrzení | Bez dvojího příjmu/platby, zachováno oddělení plánu a skutečné úhrady. |
| A15 | Reload a opakované generování dashboardu | Stabilní identity, právě jedno tlačítko a stavová karta, zachované vlastní pohledy. |
| A16 | Timeout, chyba disku a poškozená cache | Žádné tiché vymazání ověřených dat, konkrétní chyba a ověřená cesta zotavení. |
| A17 | Zastaralá predikce během chyby nového výpočtu | Zřetelné datum a stav zastarání; neprezentovat jako aktuální úplný výsledek. |

## 6. Postup a předání výsledku modelem Sol 6.1

1. Přečti pokyny projektu a toto zadání. Zkontroluj pracovní změny,
   aktuální nasazení a obnovu dat, aby nebyla přepsána novější práce.
2. Dokonči audit minulosti a inventář metod/veličin. U každé příčiny
   označ důkaz, nejistotu, závislé hodnoty a zamýšlenou opravu.
3. Navrhni datový model archivu, priority zdrojů, klíče deduplikace,
   pravidla oprav a migraci. Před implementací je popiš v dokumentaci.
4. Implementuj trvalé ukládání, ochrany nastavení, backfill, tlačítko,
   diagnostiku a logování. Přizpůsob vzor EDC konkrétním zdrojům ČEZ.
5. Doplň smysluplné regresní testy, překlady, služby, uživatelskou
   dokumentaci a synchronizované zdroje dashboardu. Spusť kontroly
   předepsané projektem a scénáře z tabulky; výsledky dolož.
6. Připrav nasaditelnou změnu a postup ověření/vrácení. Při nasazování
   respektuj aktuální rozsah uživatelova zadání; tento dokument sám
   nezakládá oprávnění měnit další integrace nebo mazat cizí data.
7. Předej změněné soubory, auditní matici, schéma závislostí, vysvětlení
   oprav, výsledky testů, zbývající omezení a stav ověření v HA.
   Simulovaný purge odliš od skutečně pozorovaného purge v provozu.

Orientační místa v tomto repozitáři: settlement_history.py (historie
a predikce), settlement.py (zálohy a pravidla), billing.py a accounting.py
(měření a náklady), coordinator.py (obnova), config_flow.py (nastavení),
sensor.py, button.py, services.yaml a __init__.py (entity a životní cyklus),
diagnostics.py, dashboard.py, dashboard_template.json a
frontend/dashboard-generator.js. Všechny uvedené zdrojové soubory jsou
pod custom_components/cez_dynamic_tariff/. Rozsah auditu odvoď také ze
skutečných volání a závislostí; seznam není omluva pro vynechání dalšího
nalezeného vstupu. Kontroly patří do tests/ a tests_homeassistant/ podle
toho, zda vyžadují běžící infrastrukturu Home Assistantu.
