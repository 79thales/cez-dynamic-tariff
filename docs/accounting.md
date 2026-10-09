# Účetnictví, zálohy a zpětný dopočet

**Vyžaduje nainstalovanou a nakonfigurovanou integraci [ČEZ HDO od Cmajda](https://github.com/Cmajda/ha_cez_distribuce), zapnutou plnou cenu a měřič importu.** ČEZ HDO ani jeho entity se nemění.

V nastavení otevřete **Období, tarif a zdroje spotřeby**. Nové senzory se přidají až po zapnutí účetnictví. Původních 39 entit zachovává ID, unique ID i význam. Doména zůstává `cez_dynamic_tariff`; mění se pouze název integrace na **ČEZ Dynamic Tariff & Accounting**.

Výchozí zúčtovací období je 1. duben až 31. březen. Začátek i konec lze změnit; konečný den se zahrnuje. Zadejte skutečné smluvní datum aktivace dynamického tarifu a skutečný začátek použití ceníku. Datum vytištěné na ceníku nemusí být začátkem vaší smlouvy.

Dokud není určený smluvní režim (finální / na zkoušku), účetnictví může zobrazit známý odběr a profil, ale neoznačí neověřený cenový model jako skutečný náklad nebo výsledek budoucího vyúčtování.

## Jednoduché zadání v nastavení (od 1.0.5)

Otevřete **Nastavení → Zařízení a služby → ČEZ Dynamic Tariff & Accounting → Konfigurovat**. Vyberte úlohu; změna zálohy už nevyžaduje průchod obdobím ani historií.

- **Zálohy po měsících – částka a potvrzení**: vyberte měsíc, zadejte zálohu a dosud zaplacenou částku. **Potvrdit plnou úhradu** doplní zaplacenou část do výše zálohy. Odeslat uloží pouze tento měsíc a zapne měsíční výpočet; dříve uložené roční součty se nesčítají s měsíci. Zde lze také zapnout automatické potvrzení k prvnímu dni měsíce.
- **Zálohy souhrnem za celé období**: volitelná alternativa, pokud znáte pouze celkový plán a zaplacený součet. Uložení tohoto formuláře zapne souhrnný režim. Měsíční řádky zůstanou zachované.
- **Zpětný dopočet a počáteční stav**: historie se přebírá automaticky. Pokud chybí starší údaje, zvolte **Zadat ověřený součet z faktury / ČEZ** a opište datum, kWh a náklady včetně jističe a poplatků pro stejné zúčtovací období. Nepatří sem stav elektroměru, zálohy ani faktura z jiného období. Součet se převezme jednou a novější historie se přičte od následujícího dne.

Neznámý odečet nemá předvyplněné nulové částky. **Použít historii Home Assistantu** vypne ruční počáteční stav a používá dostupné statistiky. Původní senzory a historie zůstávají zachované. Ruční součet lze opsat z PDF; tato volba sama PDF neskenuje. JSON není součástí běžného nastavení.

## Měsíční karta záloh (od 1.0.4)

Karta je součástí integrace a načte se při instalaci aktualizace; další frontend balíček není potřeba. Po aktualizaci obnovte stránku HA a přidejte:

```yaml
type: custom:cez-advances-card
entity: sensor.cez_dynamic_tariff_accounting_status
title: Zálohy
```

Každý měsíc má **Záloha**, **Zaplaceno**, zbývající částku, **Uložit** a **Potvrdit**. Uložit zachová i částečnou úhradu (např. z 2 500 Kč zaplaceno 1 700 Kč, zbývá 800 Kč); Potvrdit označí celou částku. Opravu nebo zrušení provedete změnou zaplacené částky a uložením. Nezadávané měsíce nejsou nuly. Měsíční plán začne ovlivňovat odhad po výslovném zapnutí volby použití měsíčních záloh a uložení řádku; dosavadní roční součet se na měsíce nerozpočítává.

**Automatické potvrzení k prvnímu dni v měsíci** je výchozí vypnuté. Zapnutí uprostřed měsíce platí od příštího měsíce; zapnutí prvního platí už pro tento měsíc. Po výpadku HA se doplní jen splatné známé měsíce od tohoto zapnutí. Minulé platby před zapnutím, neurčené částky, ruční opravy a částečné úhrady se nepřepisují. Opakovaná aktualizace nebo restart nepřičte stejnou platbu znovu. Karta rozlišuje **Zaplaceno**, **Částečně zaplaceno**, **Nezaplaceno**, **Automaticky potvrzeno** a **Nezadáno**.

Potvrzení je evidence v HA, ne bankovní platba ani ověření přijetí platby u ČEZ. Částky zůstávají lokálně. Akce `cez_dynamic_tariff.update_advance` a `cez_dynamic_tariff.set_automatic_advances` jsou dostupné i pro automatizace; služby nevytvářejí další elektroměry ani nemění původní entity.

Volba **Elektroměr importu pro účetnictví** umožní vybrat stejné měření jako v Energy, například „Meter Total Energy (import)“, a zachovat zdroj původního monitoringu. Náklady původního monitoringu se přebírají pouze při shodném elektroměru; náklady z jiného zdroje by zkreslovaly výsledek.

## Co se přebírá a co se dopočítává

Import v kWh používá již opravené přírůstky dlouhodobých statistik Home Assistantu. Neresetuje ani nekopíruje původní elektroměr. Automatický zdroj nákladů přebírá již vypočtené peněžní statistiky `actual_cost`; záznamy s neoceněným odběrem a první částečná hodina se nepovažují za plně oceněné.

Volitelný vlastní nákladový senzor musí poskytovat CZK pouze za odebranou elektřinu, bez stálých plateb. Výběrem potvrzujete, že zdroj používá správné smluvní ceny. Senzor vzniklý ze staré nesprávné fixní ceny pro zpětné ocenění vhodný není.

Chybějící náklady se dopočítají pouze s platným historickým cenovým profilem a dochovaným veřejným rozvrhem HDO. Hodinový odběr se rozdělí rovnoměrně uvnitř hodiny; dnešní záznamy měřidla používají stejná pravidla jako původní účetnictví (rovnoměrně uvnitř intervalu nejvýše 15 minut). Chybějící HDO se nepovažuje za VT, chybějící spotřeba za nulu ani dnešní ceník za platný v minulosti. Staré smazané detailní záznamy se nedají přesně obnovit z pouhého měsíčního součtu.

Nové účetnictví obnovuje dnešek od místní půlnoci. Původní `daily_cost` nadále znamená náklady zachycené původním ledgerem; pro nový dashboard slouží `daily_cost_backfilled`. Oba výsledky se nesčítají. Historie se načítá a zpracovává jednou za pět minut v executor vlákně Recorderu. Stav obsahuje čas posledního dopočtu a úplnost pokrytí.

## Dynamický tarif a tarif na zkoušku

Procentní změna se týká pouze obchodní ceny za kWh. Distribuce, daně a stálé platby se nemění. [ČEZ zároveň rozlišuje finální tarif a doplněk na zkoušku](https://www.cez.cz/cs/nova-energetika/dynamicky-tarif).

Ve finálním režimu nové účetnictví používá nastavenou dynamickou cenu. V režimu **na zkoušku** fakturovaný odběr používá standardní ceny NT/VT. Již vypočtený standardní náklad se získá ze součtu původního nákladu a původní úspory; nepřepočítává se podruhé. Budoucí dodatečně vyplacená úspora není automaticky odečtena. ČEZ pro její výpočet používá váženou obchodní cenu NT/VT a celé zkušební období s ochranou před celkovým příplatkem. Původní denní simulace podle jednotlivé obchodní ceny NT/VT není potvrzenou částkou této vratky. Nová denní úspora na zkoušku zůstává neznámá; nula by tvrzení o vratce zkreslila.

## Zálohy

Zvolte součet za celé období a již zaplacenou část, nebo jednotlivé měsíce. Platby se samy neoznačují jako zaplacené. V měsíčním režimu nevyplněný měsíc znamená chybějící údaj; nula výslovně žádnou zálohu. Dokud některý měsíc chybí, nezobrazuje se výsledný přeplatek, který by vycházel jen z částečného plánu. Roční součet umožňuje zadat ověřený úplný plán bez vymýšlení měsíčních dat.

`forecast_balance = advance_payments_total - forecast_net_cost`: kladná částka je předpokládaný přeplatek, záporná nedoplatek. Již zaplacené zálohy jsou samostatný senzor; plán není stavem bankovních plateb.

## Existující příjem ze sdílení

Přepínač **Odečíst již vypočtený příjem ze sdílení** je ruční. Vyberte peněžní senzor nebo EDC zdroj s atributem `energy_revenue_statistic_id`. Integrace čte jeho existující finanční statistiku v CZK; nepřepočítává sdílené kWh prodejní cenou a nesčítá příjem všech příjemců podruhé. Vybraný zdroj má odpovídat placeným příjemcům.

Příjem se přiřazuje ke dni, ke kterému náleží. Předvčerejší příjem se nikdy neodečte od dneška. Bez dnešních dat je dnešní čistý náklad neznámý. Pro celkové období a výhled se odečítá pouze známý příjem a zobrazuje datum jeho dostupnosti. Budoucí příjem se neodhaduje. Náklady elektřiny a výnos ze sdílení zůstávají oddělené položky.

## Ověřený odečet a předchozí vyúčtování

Volitelný odečet dodavatele zadává kumulovaný odběr a kumulované náklady **včetně stálých plateb**, od začátku právě vybraného období do uvedeného dne. Tyto již spočítané hodnoty se převezmou; statistiky se přidávají až od následujícího dne. Při změně začátku období se starý odečet nepřenáší. Pokud vypnete stálé platby, jejich známá historická část se z převzatého nákladu odečte.

Dříve uložená ověřená vyúčtování, měsíční profily a historické ceníky zůstávají zachované. Změna zálohy ani počátečního stavu je nepřepisuje. Již ověřené faktury se nepřeceňují současným ceníkem. Pro běžný zpětný dopočet ani pro zálohy nemusíte připravovat JSON.

## Odhad a jeho meze

Profil používá měsíční denní průměry z úplných historických dní, s 23/25 hodinami při změně času. Chybějící hodiny a současný rozpracovaný den průměr nesnižují. Pokud pro budoucí zimní měsíc nejsou úplné dny ani měsíční údaje staršího vyúčtování, zimní odběr se nevymýšlí z léta a prognóza zůstává neúplná.

Odhad nákladů doplňuje známou spotřebu sezónním odhadem zbývajících dní a průměrnou cenou nynějšího dvoudenního cenového výhledu. Změny počasí, fotovoltaiky, baterie, rozložení spotřeby mezi pásma a budoucích ceníků tím nejsou předpovězené. Výsledek je odhad, nikoliv budoucí faktura. Úplnost skutečných vstupů a použitá cenová metoda jsou v atributech. Ověřená předchozí faktura a dnešní odhad mají v dashboardu odlišné popisky.

Platby, odečty a starší vyúčtování se uchovávají lokálně v nastavení Home Assistantu; diagnostika je rediguje. Soubory zákazníka se nesmějí publikovat v repozitáři ani release artefaktu.
