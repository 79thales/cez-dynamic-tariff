# Správa vyúčtování, ceníků a orientačního ocenění

## Kde administraci otevřít

V Home Assistantu otevřete **Nastavení → Zařízení a služby → ČEZ Dynamic
Tariff & Accounting → Konfigurovat → Vyúčtování a ceníky**.

Administrace používá nativní formuláře HA a stejné options jako účetní
výpočet. Přehled ukazuje podklady skutečně uložené v integraci. Samotný
soubor nalezený v pracovní složce není automaticky importovanou fakturou.

Na detailním dashboardu je také tlačítko odkazující na nastavení integrace.
Tři pohledy (hlavní přehled, detaily a pomocný editor záloh) zůstávají
zachované. Generate dashboard i dodávaná šablona obsahují stejná upozornění.

## Vyúčtování

Vyberte **Vyúčtování**, nový nebo uložený záznam a akci přidat/upravit.
Zadejte zdroj podkladu, uzavřené období, celkové kWh, VT, NT a celkové
náklady s DPH. VT + NT musí odpovídat celkové energii s tolerancí 0,01 kWh.
Volitelné zaplacené zálohy a zahrnuté stálé platby mohou zůstat prázdné;
prázdná hodnota není nula. Stálé platby nesmějí překročit celkové náklady.

Měsíční rozpis lze upravit před konečným uložením. Každý známý celý měsíc
potřebuje NT i VT; prázdná dvojice zůstává neznámá. Nulu zadávejte pouze
pro doložený nulový odběr. Částečné krajní měsíce nelze použít jako celoměsíční
sezónní profil. Úplný rozpis musí odpovídat součtům faktury; částečný je
nesmí překročit. Starší měsíční metadata zůstávají při úpravě zachovaná,
pokud výslovně nezvolíte odstranění nebo úpravu měsíčního rozpisu.

Faktury se nesmějí časově překrývat. Celkový součet faktury nahrazuje
dosavadní výpočet jen při přesné shodě celého zúčtovacího období.
Měsíční rozpis slouží jako záloha sezónního profilu tam, kde chybí úplné
dny Recorderu. Faktura se nepřičítá jako další odběr ke kontrolnímu odečtu.

Odstranění vyžaduje potvrzení. Smazání faktury zvolené jako zdroj poměru
VT/NT zároveň vypne náhradní ocenění. Ověřený archiv energie a nákladů
se tím nemaže. Změna období vybrané faktury aktualizuje odkaz pro odhad.

## Ceníky a jejich platnost

**Historické ceníky** obsahují sazby s DPH v Kč/kWh a Kč/měsíc, zdroj a
platnost od–do včetně obou dní. Všechny složky jsou explicitní, včetně
doložených nul. Výpočet je znovu nezvyšuje o DPH. Všechna čísla musejí
být konečná a nezáporná; nepodporovaná záporná sazba se odmítne.

Nový historický ceník lze zadat ručně, načíst existujícím importem ČEZ PDF
nebo výslovně převzít aktivní sazby jako návrh. Kopie aktivních sazeb není
důkaz jejich historické platnosti: datum a hodnoty musí uživatel ověřit.
PDF import zachovává původní omezení velikosti, formátu a HTTPS zdrojů.
Před uložením se ukážou sazby, zdroj i obchodní a distribuční účinnost.
Začátek společného profilu je nejdříve pozdější z obou účinností; datum lze
v editoru upravit podle skutečně doložené smlouvy. Import do historie
nemění aktivní ceny, jistič ani současné nastavení.

Historické profily se nesmějí překrývat navzájem ani s aktivním ceníkem.
Aktivní ceník je v nynějším modelu otevřený od nastaveného začátku platnosti;
jeho sazby upravuje volba **Aktivní ceník – upravit sazby**, datum se
spravuje v nastavení období. Hlavní volba importu PDF nadále mění aktivní
ceník. Přehled historie ukazuje konkrétní kalendářní mezery v cenách za
dosavadní zúčtovací období. Mezery jsou dovolené, ale nevytvářejí nulové
ceny a blokují ocenění příslušného odběru.

## Volitelné orientační ocenění

Výchozí nastavení náhradní ocenění **vypíná**. V části **Nastavení
orientačního ocenění** lze zvolit vyúčtování uzavřené před začátkem
současného období. Musí mít nenulový celkový odběr a doložené rozdělení NT/VT.
Starší formát bez celkových NT/VT lze použít, pokud jejich součty z
měsíčního rozpisu odpovídají celkové energii faktury.

Pro neoceněnou energii se použije poměr:

- podíl NT = NT faktury / (NT faktury + VT faktury);
- náhradní cena = podíl NT × platná cena NT + podíl VT × platná cena VT;
- náhradní náklad = pouze dosud neoceněné kWh × náhradní cena.

Ceník se vybírá podle místního data odběru. Dynamická změna upravuje jen
obchodní složku, podle doloženého smluvního režimu a data aktivace.
Minutový průměr známých místních pásem uvnitř intervalu zachovává skutečný
uplynulý čas v UTC i při změně letního času. U částečně oceněné hodiny se
průměrná náhradní cena používá pouze pro zbývající neoceněné kWh. Proto
je i tento výpočet aproximací, nikoli zjištěným historickým HDO.

Výhled obsahuje ověřené dosavadní náklady, samostatnou náhradně oceněnou
část a budoucí spotřebu podle sezónního profilu. Budoucí cena používá
existující průměr dostupného aktuálního cenového výhledu; jde o předpoklad
pokračování současných cen, nikoli záruku budoucích smluvních cen.
Kontrolní odečet je zahrnut jednou, další výpočet začíná následujícím dnem.
Příjem ze sdílení se odečítá podle původního nastavení, pouze ve známé výši.

Náhradní část nikdy nemění přesné period_gross_cost, účetní úplnost, HDO
ani archiv ověřených nákladů. Metadata uvádějí metodu, zdrojové období,
podíl NT, náhradní kWh a Kč. Hlavní a detailní dashboard zobrazují upozornění
**Orientační odhad – část spotřeby oceněna náhradním výpočtem**.

Chybějící historie spotřeby, chybějící platný ceník, stálé sazby, neznámý
smluvní režim nebo chybějící sezónní profil odhad zablokují. Odhad se také
nezobrazí při konfliktu nebo neplatnosti zdrojových dat či selhání archivu.
Upozornění vysvětlí konkrétní důvod. Chybějící údaje nejsou nula.

## Kontrola, souběh a restart

**Kontrola a přepočet** ukazuje poslední runtime stav: počet bloků,
neoceněné kWh, pokrytí energie, chybějící stálé sazby a časové intervaly
neoceněného odběru s rozlišením chybějící ceny a HDO. Bez načtené integrace
uvádí neověřený stav, nikdy předstíranou nulu.

Zaškrtnutí **Spustit přepočet dostupné historie** vyvolá původní akci
cez_dynamic_tariff.backfill_accounting s konkrétním entry_id. Přijetí
akce není dokončení výpočtu. Pro obnovení zobrazení kontrolu znovu otevřete.
Původní sdílený zámek brání souběžnému pravidelnému a ručnímu přepočtu.
Zůstává zachovaný archiv a mechanismus pokračování po přerušení;
po restartu případně znovu spusťte přepočet.

Editor ukládá celý změněný seznam atomicky až po úspěšné validaci.
Rozpracovaný formulář není uložená faktura. Pokud jiný formulář mezitím
změní účetní podklady, starý editor zápis odmítne a požádá o nové otevření.
Ostatní options včetně záloh a kontrolního odečtu se zachovávají.

Diagnostika nově obsahuje také neoceněné časové intervaly a důvody blokace
výhledu. Úplné faktury a zákaznické částky nadále podléhají redakci diagnostiky.
Soukromé faktury ani zákaznické konfigurační soubory nepatří do veřejného
repozitáře nebo instalačního balíčku.

## Rozsah této změny

Univerzální OCR faktur ani obecný import libovolného dodavatelského PDF není
součástí administrace. Dříve dodané místní podklady lze využít pro ověření
a vyplnění; do živého HA se nedostanou pouhou přítomností na disku.
Nasazení a kontrola skutečných zákaznických dat jsou samostatným krokem
po dokončení a ověření implementace.

Historické rozvrhy stejné revize se sjednocují podle skutečného pokrytí.
Odstranění minulého dne ze zdrojového seznamu po půlnoci není konflikt.
Rozdílné NT/VT v překrývajícím se časovém intervalu se nadále odmítne;
taková odpověď nepřepíše ověřený archiv a blokuje finanční výhled.
