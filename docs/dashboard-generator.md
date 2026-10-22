# Generate dashboard

Od verze **1.0.8** najdete tlačítko **Generate dashboard** na zařízení integrace
ČEZ Dynamic Tariff & Accounting. Stejnou volbu najdete v **Nastavení → Zařízení
a služby → ČEZ Dynamic Tariff & Accounting → Konfigurovat → Generate dashboard**.
Tlačítko vytvoří oznámení s odkazem na generátor, obdobně jako v EDC Share.

1. Otevřete generátor jako správce Home Assistantu.
2. Ponechte nebo změňte název a adresu pohledu.
3. Klikněte na **Generate dashboard · náhled**.
4. Klikněte na **Přidat do horní lišty**. Hlavní pohled se přidá do horní lišty
   existujícího **Overview (`/lovelace`)**. Detaily a pomocný editor záloh jsou podstránky.

Generátor používá současné složení: aktuální cena, dnešní náklady a úspory,
vyúčtování, skutečný měsíční odběr, nejlevnější odběr. Zachovává také složení
detailů. Pokud už pohledy ČEZ existují, náhled převezme jejich přesné místní
složení včetně vašich úprav. Při převzetí opraví staré výrazy
`is_state(hdo, 'on'/'off')` ve šablonách s atributem `hdo_entity`: stav čte až
po ověření řetězce a platného ID. Chybějící HDO znamená **neznámé**;
`on` zůstává NT a `off` VT. Pro novou instalaci slouží opravená dodaná šablona.
Grafy používají **ApexCharts Card**, stejně jako současný přehled;
generátor tuto kartu neinstaluje. Pokud chybí, nainstalujte ji přes HACS sami.
Pomocný editor záloh je součástí integrace.

Editor záloh se registruje také jako **JavaScript module** mezi zdroji
dashboardů. Jeho URL má tvar `/cez_dynamic_tariff/advances-card.js?v=<verze>`;
hodnota pochází z `manifest.json` načteného loaderem Home Assistantu.
Nové vydání proto změní URL automaticky, například z `?v=1.0.9` na
`?v=1.0.10`. Reload doplní chybějící zdroj nebo aktualizuje jeho verzi
pod stejným ID. Přehled, detailní podstránky ani evidence záloh se tím nemění.
Automatické načtení přes úvodní HTML zůstává zachováno se stejnou URL.
YAML zdroje se automaticky neupravují; případný pokyn se objeví v logu HA.

Chyba **Custom element doesn't exist: cez-advances-card** znamená, že prohlížeč
nenačetl soubor editoru. U již spuštěné instalace lze zdroj doplnit v
**Nastavení → Dashboardy → nabídka ⋮ → Zdroje → Přidat zdroj**. Pro ruční opravu
použijte `/cez_dynamic_tariff/advances-card.js` a typ **JavaScript module**
(text `<verze>` do URL nezadávejte). Pokud zdroj již existuje, upravte jeho URL
a typ místo vytvoření další položky. Po změně obnovte stránku pomocí Ctrl+F5.
U starší integrace lze stejný soubor načíst ručně; není třeba měnit podmíněnou
kartu, částky záloh, platby ani regenerovat celý dashboard.

Také URL **Generate dashboard** používá verzi integrace z manifestu pro soubor
`frontend/dashboard-generator.js`. Změna JS bez změny verze URL nezmění;
při ruční opravě ve stejné verzi může být nutné vymazat cache prohlížeče.
Složení přehledu, detailů a pomocného editoru
se nadále bere z přibalené šablony nebo zachovaných místních pohledů. Po výměně
Python souborů integrace ve stejné revizi je nutný restart HA; samotný reload
config entry nové Python moduly do paměti nenačte. Potom obnovte prohlížeč.

Náhled ukáže nedostupné entity. Používá skutečná ID registru včetně přejmenování
a zvoleného HDO zařízení. Údaje nejsou kopírované z jiné domácnosti; účetnictví,
zálohy, historie a srovnání s fakturou čtou existující senzory a uložené údaje.
Vyžaduje nakonfigurované ČEZ HDO. Pro finanční přehled zapněte ocenění a účetnictví
v nastavení ČEZ.

Existující pohledy, pořadí, témata a další nastavení dashboardu se zachovají.
Pokud některá ze tří adres existuje, nepřepíše se a nevznikne duplicitní kopie.
Generátor nabídne odkaz na existující pohled; jiný nový pohled vyžaduje jinou adresu.
Při změně Overview během přidávání se uložení zastaví a lze jej zopakovat.
Při výpadku spojení se ověřuje výsledek zápisu; žádný pohled se automaticky nemaže.

Oprava generátoru sama nepřepíše již uložený pohled. Pro opravu existující karty
otevřete `/lovelace/cez-dynamic-tariff`, v části **Aktuální cena** upravte markdown
kartu **Cena odebrané kWh** a její YAML nahraďte obsahem
[`examples/hdo_status_card.yaml`](../examples/hdo_status_card.yaml).
Ostatní karty a podstránky ponechte. U přejmenovaných senzorů zachovejte svá ID.
Alternativně stáhněte náhled generátoru a převezměte z něj opravenou kartu.
Uložení karty nepotřebuje restart HA; po aktualizaci souboru generátoru obnovte
prohlížeč bez cache. Podrobnosti a rozsah ověření obsahuje
[report opravy logu 2026.10](ha-2026-10-log-fixes.md).

**YAML spravovaný nebo automaticky generovaný Overview se nepřebírá automaticky.**
YAML můžete stáhnout. Obsahuje klíč `views` se třemi pohledy; při ručním přidání
připojte tyto položky ke stávajícím `views`. Nenahrazujte celou konfiguraci
Overview tímto fragmentem. U automatického Overview nejdříve použijte funkci
Home Assistantu pro převzetí do ruční správy.

## Maintenance / údržba

Účetní Apex grafy používají sdílený tooltip, který spojuje body podle skutečného
času X (milisekundy), nikoli podle pořadí v sérii. U měsíčního měření vypíše pouze
modrý **Úplný měsíc** nebo oranžový **Neúplný měsíc**, podle uloženého pokrytí.
`null`, chybějící bod a neplatné číslo se nevypisují; platná nula se zobrazí jako
`0,0 kWh` nebo `0,0 Kč`. Nejde o data předchozího roku. Neaktivní série skryté
kliknutím na legendu se do tooltipu nezařazují. Názvy sérií se HTML escapují.
Stejný formatter opravuje prázdné body skutečnosti/odhadu v detailu a hranice
finančního grafu. Neinterpoluje ani nepřebírá hodnotu z jiného času.

Měsíční datum tooltipu používá měsíc/rok UTC, protože X měsíčních generátorů je
výslovně poledne UTC prvního dne měsíce; finanční datum zobrazuje také den podle
časového pásma prohlížeče, stejně jako existující finanční generátory. Měsíční
rozlišení aktuálního měsíce se nadále řídí `hass.config.time_zone` (výchozí
Europe/Prague). Rozsahy grafů a účetní výpočty formatter nemění. Vlastní tooltip
se spouští pouze při ukázání na graf; neprovádí žádný síťový zápis a při neplatném
X nebo bez platných hodnot vrátí prázdný obsah.

Nepoužíváme `hideEmptySeries: true`: [dokumentace ApexCharts](https://apexcharts.com/docs/options/tooltip/)
uvádí, že tato volba skrývá také nuly. Při převzetí místních pohledů generátor
vymění jen tooltip tří známých účetních Apex karet podle typu a přesného nadpisu
za aktuální přibalenou verzi. Entity, názvy sérií, faktury, pořadí karet a sekce
zůstanou místní. Komentáře jsou uvnitř EVAL funkce a zachovají se v JSON/YAML
exportu i při uložení konfigurace. Již uložený dashboard se samotnou aktualizací
integrace nepřepíše; cílená oprava karty je samostatný zápis.

`custom_components/cez_dynamic_tariff/dashboard_template.json` je zdroj aktuálního
složení. Při každé úpravě dashboardu aktualizujte také tuto šablonu a generátor.
Osobní PDF, částky, odečty a adresy elektroměrů do veřejné šablony nepatří.

The configuration button opens a preview/YAML generator, following the EDC Share
workflow. Direct creation adds a view to the existing Overview's top tab bar,
with two subviews. It does not create a sidebar dashboard. Administrator access
is required. Existing views and settings are preserved; duplicate paths are
rejected. The layout matches the current ČEZ dashboard, using registry-resolved
entities and existing statistics. ApexCharts Card and configured ČEZ HDO are
required. YAML exports contain three `views` to append, not a replacement for
the whole Overview configuration. Keep the bundled template and generator in
sync with every layout change.

## Cenové režimy od 1.1.0

Přehled obsahuje registrovaný volič strategie a semafor aktivní obchodní ceny.
Pevný režim ukazuje Kč/kWh, procentní také procentní změnu. Celková cena a
výhled zahrnují HDO. Generátor při náhledu stávající sestavy upraví známé cenové
karty a přidá právě jeden volič; jiné místní karty a podstránky zachová. Již
uložené pohledy zůstávají beze změny až do ručního převzetí karet z náhledu.
Podrobnosti: [dva cenové režimy](dynamic-pricing-1.1.md).

## Vyúčtování a ceníky (připraveno pro 1.0.12)

Hlavní i detailní vyúčtování obsahují označení náhradního historického
ocenění, jeho kWh, Kč a zdrojovou fakturu. Při chybějících podkladech
vysvětlí důvody blokace. Detail obsahuje odkaz na nastavení integrace,
kde je nová administrace **Vyúčtování a ceníky**.

Generate dashboard upravuje stejné části jako dodávaná šablona.
Při převzetí místních pohledů doplní označený blok do účetních souhrnů
a jeden odkaz do detailu. Opakovaný náhled blok ani tlačítko neduplikuje;
ostatní karty, místní entity a tři dosavadní pohledy zachová.
Samotná aktualizace integrace nepřepisuje uložený Lovelace dashboard.
