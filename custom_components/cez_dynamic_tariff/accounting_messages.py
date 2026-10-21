"""České vysvětlení příčin pro kontrolu podkladů a generovaný dashboard."""

REASONS = {
    "historical_hdo_missing": "Chybí historické rozdělení VT/NT (HDO).",
    "historical_price_missing": "Pro datum spotřeby není uložený platný ceník.",
    "price_profile_missing": "Chybí sazby stálých plateb pro část období.",
    "energy_history_gap": "Historie spotřeby není úplná; chybějící odběr nelze pokládat za nulu.",
    "today_energy_gap": "Dnešní historie odběru není úplná.",
    "future_price_missing": "Pro výhled chybí úplný cenový podklad.",
    "estimate_not_enabled": "Náhradní ocenění je vypnuté. Zdroj poměru VT/NT lze zvolit v nastavení odhadu.",
    "estimate_bill_invalid": "Vybrané starší vyúčtování nemá použitelný poměr VT/NT.",
    "unpriced_intervals_missing": "Chybí časové rozlišení neoceněného odběru.",
    "accounting_incomplete": "Přesné účetnictví zůstává neúplné.",
    "contract_unconfirmed": "Není potvrzen smluvní režim nebo datum aktivace dynamického tarifu.",
    "consumption_profile_missing": "Chybí sezónní profil spotřeby pro část budoucího období.",
}
