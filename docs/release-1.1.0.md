# Vydání 1.1.0 – podklady k nasazení

Vydání spojuje oba cenové režimy s dosud místně nasazenou administrací
účetnictví 1.0.12. Obsahuje její ověřené změny z větve `codex/accounting-admin`
a opravu interního zápisu HA Store pro HA 2025 i 2026. Nové GPL licenční
soubory z veřejné větve zůstávají zachované.

## Ověření před vydáním

- 125 jednotkových testů, 128 lifecycle testů proti skutečnému HA 2025.1.4.
- 29 testů JavaScriptu, Ruff a kontrola rozdílů bez chyby.
- Oba původně dodané PDF ceníky mají ověřené čtyři rozvrhy a ceny.
- Společná sada zahrnuje historickou administraci a zákaz převodu pásmového
  ceníku do historické tabulky jediné sazby NT/VT. Odmítnutí nic neaktivuje.
- Quality kontroluje také HA 2026.8.3 a aktuální stabilní vydání.
  Výsledky pro přesný commit jsou v GitHub Actions; lokální běh je nenahrazuje.

## Záloha a instalace

Před výměnou kódu vznikla soukromá záloha integrace, jejích config entries
bez cizích účtů a všech vlastních účetních Store. Kopie je na disku H:
v adresáři `01.programovani/04.HA/cez-release-1.1.0-20261022`.
SHA-256 archivu před instalací:
`70799d490a6e7a4b274ab98a64ed639eb68bde7c9763c986c687a6b2e469ba65`.
Finanční obsah zálohy ani přiložené zákaznické dokumenty nejsou součástí Gitu.

Instalátor se sestavuje z neměnného commitu odpovídajícího tagu `v1.1.0`.
Před restartem je třeba ověřit hash přeneseného ZIP, všechny rozbalené
soubory a konfiguraci HA. Instalace nemění smluvní profil, sazby ani
options; po restartu se kontroluje jejich zachování a stav integrace.
Samotné zavedení nového modulu nepřepisuje uložený dashboard.

## Návrat

Při chybě setupu lze obnovit původní adresář kódu ze soukromé zálohy
 a restartovat HA. Config entries a účetní Store se automaticky nevracejí:
přepsání nových finančních dat starší kopií by mohlo ztratit nová měření.
Nejprve se porovná jejich obsah a zachová novější archiv. Neprovádí se purge,
změna elektroměru ani přepočet smluvních účinností.

Konečný výsledek nasazení, hash publikovaného instalátoru a kontrola
živého HA se ukládají soukromě vedle zálohy. Veřejný release obsahuje
pouze české uživatelské poznámky a instalační ZIP.
