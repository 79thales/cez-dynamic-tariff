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
složení včetně vašich úprav. Pro novou instalaci slouží dodaná šablona.
Grafy používají **ApexCharts Card**, stejně jako současný přehled;
generátor tuto kartu neinstaluje. Pokud chybí, nainstalujte ji přes HACS sami.
Pomocný editor záloh je součástí integrace.

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

**YAML spravovaný nebo automaticky generovaný Overview se nepřebírá automaticky.**
YAML můžete stáhnout. Obsahuje klíč `views` se třemi pohledy; při ručním přidání
připojte tyto položky ke stávajícím `views`. Nenahrazujte celou konfiguraci
Overview tímto fragmentem. U automatického Overview nejdříve použijte funkci
Home Assistantu pro převzetí do ruční správy.

## Maintenance / údržba

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
