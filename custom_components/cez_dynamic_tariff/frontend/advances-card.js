/* Monthly bookkeeping UI. All financial data stays in the user's Home Assistant. */
class CezAdvancesCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._drafts = new Map();
    this._busy = false;
  }

  setConfig(config) {
    this._config = { entity: "sensor.cez_dynamic_tariff_accounting_status", ...config };
    this._signature = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    const a = hass.states[this._config.entity]?.attributes;
    const signature = JSON.stringify(a && [a.billing_start, a.billing_end,
      a.monthly_advances, a.advance_mode, a.automatic_advances,
      a.automatic_advances_from]);
    if (signature !== this._signature) {
      this._signature = signature;
      this._render();
    }
  }

  getCardSize() { return 12; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: 14 }; }

  _node(tag, text, cls) {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }

  async _call(service, data, month) {
    if (this._busy) return;
    this._busy = true;
    this._error = "";
    const buttons = this.shadowRoot.querySelectorAll("button,input");
    buttons.forEach(b => { b.disabled = true; });
    try {
      await this._hass.callService("cez_dynamic_tariff", service, {
        entry_id: this._hass.states[this._config.entity].attributes.entry_id,
        ...data,
      });
      if (month) this._drafts.delete(month);
      this._notice = "Uloženo do evidence záloh.";
    } catch (error) {
      this._error = error.message || "Změnu se nepodařilo uložit.";
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _render() {
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = this._node("style");
    style.textContent = `
      :host{display:block;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,Arial,sans-serif)}
      ha-card{display:block;padding:20px;border-radius:var(--ha-card-border-radius,16px);background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#e1e5e8)}
      h2{font-size:24px;font-weight:500;margin:0 0 8px}p{line-height:1.45;margin:8px 0 16px;color:var(--secondary-text-color)}
      .settings{display:flex;gap:10px;align-items:flex-start;padding:12px;background:var(--secondary-background-color);border-radius:10px;margin:12px 0}
      .settings input{margin-top:4px;accent-color:var(--primary-color);width:18px;height:18px;flex:none}
      .settings small{display:block;color:var(--secondary-text-color);line-height:1.4;margin-top:4px}
      .row{border-top:1px solid var(--divider-color);padding:14px 0}
      .heading{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:10px;font-weight:500}
      .badge{font-size:12px;border-radius:20px;padding:4px 9px;background:var(--secondary-background-color);white-space:nowrap}
      .paid{color:#13743b;background:#dff1e5}.partial{color:#915c00;background:#fff0cf}.auto{color:#65509b;background:#eee8fb}
      .fields{display:grid;grid-template-columns:1fr 1fr;gap:10px}label{font-size:13px;color:var(--secondary-text-color)}
      input[type=number]{box-sizing:border-box;width:100%;min-width:0;margin-top:4px;padding:10px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit;font-size:16px}
      .actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}.remaining{margin-right:auto;font-size:13px;color:var(--secondary-text-color)}
      button{font:inherit;border:1px solid var(--primary-color);border-radius:8px;padding:8px 12px;background:transparent;color:var(--primary-color);cursor:pointer}
      .confirm{color:var(--text-primary-color,#fff);background:var(--primary-color,#007aa3)}button:disabled,input:disabled{opacity:.55;cursor:default}
      .error{color:var(--error-color,#b00020);margin:12px 0;line-height:1.4}.notice{color:var(--secondary-text-color);font-size:13px;margin-top:12px}
    `;
    root.append(style);
    const card = this._node("ha-card");
    root.append(card);
    card.append(this._node("h2", this._config?.title || "Zálohy"));
    const a = this._hass?.states[this._config?.entity]?.attributes;
    if (!a || !Array.isArray(a.monthly_advances)) {
      card.append(this._node("p", "Měsíční editor vyžaduje ČEZ Dynamic Tariff & Accounting 1.0.4 a zapnuté účetnictví."));
      return;
    }
    card.append(this._node("p", `${a.billing_start} → ${a.billing_end}`));
    const modeLabel = this._node("label", undefined, "settings");
    const useMonthly = this._node("input");
    useMonthly.type = "checkbox";
    useMonthly.checked = this._monthlyChoice ?? (a.advance_mode === "monthly");
    useMonthly.addEventListener("change", () => { this._monthlyChoice = useMonthly.checked; });
    const modeText = this._node("span", "Použít měsíční zálohy pro výpočet");
    modeText.append(this._node("small", "Zapněte, pokud má vyúčtování používat součet vyplněných měsíců. Volba se uloží s měsíční částkou."));
    modeLabel.append(useMonthly, modeText);
    card.append(modeLabel);
    if (a.advance_mode === "annual") card.append(this._node("p", "Výpočet zatím používá samostatně zadaný roční součet. Měsíční řádky mohou být vyplněné nezávisle."));

    const autoLabel = this._node("label", undefined, "settings");
    const auto = this._node("input");
    auto.type = "checkbox";
    auto.checked = !!a.automatic_advances;
    auto.addEventListener("change", () => this._call("set_automatic_advances", { enabled: auto.checked }));
    const autoText = this._node("span", "Automaticky potvrdit vždy k 1. dni v měsíci");
    autoText.append(this._node("small", a.automatic_advances_from
      ? `Od ${a.automatic_advances_from}. Automatická evidence neověřuje bankovní platbu. Ruční opravy a částečné úhrady zůstávají zachované.`
      : "Výchozí vypnuto. Zapnutí uprostřed měsíce začne příštím měsícem; nepotvrdí starou historii."));
    autoLabel.append(auto, autoText);
    card.append(autoLabel);

    const rows = new Map(a.monthly_advances.map(r => [r.month, r]));
    const first = /^([0-9]{4})-([0-9]{2})/.exec(a.billing_start);
    const last = /^([0-9]{4})-([0-9]{2})/.exec(a.billing_end);
    if (!first || !last) return;
    let year = Number(first[1]), m = Number(first[2]);
    const finish = Number(last[1]) * 12 + Number(last[2]);
    for (let count = 0; year * 12 + m <= finish && count < 24; count++) {
      const month = `${year}-${String(m).padStart(2, "0")}`;
      const row = rows.get(month);
      const paid = row ? Number(row.paid_amount ?? (row.paid ? row.amount : 0)) : 0;
      const block = this._node("div", undefined, "row");
      const heading = this._node("div", undefined, "heading");
      const name = new Date(year, m - 1, 1).toLocaleDateString("cs-CZ", { month: "long", year: "numeric" });
      heading.append(this._node("span", name));
      const status = !row ? "Nezadáno" : row.paid
        ? row.paid_source === "automatic" ? "Automaticky potvrzeno" : "Zaplaceno"
        : paid > 0 ? "Částečně zaplaceno" : "Nezaplaceno";
      heading.append(this._node("span", status, `badge ${row?.paid_source === "automatic" ? "auto" : row?.paid ? "paid" : paid > 0 ? "partial" : ""}`));
      block.append(heading);
      const fields = this._node("div", undefined, "fields");
      const inputs = {};
      for (const [key, label, value] of [["amount", "Záloha (Kč)", row?.amount], ["paid_amount", "Zaplaceno (Kč)", row ? paid : undefined]]) {
        const field = this._node("label", label);
        const input = this._node("input");
        input.type = "number"; input.min = "0"; input.step = "0.01"; input.inputMode = "decimal";
        input.setAttribute("aria-label", `${label} — ${name}`);
        input.value = this._drafts.get(month)?.[key] ?? (value ?? "");
        input.placeholder = "Nezadáno";
        input.addEventListener("input", () => {
          this._drafts.set(month, { amount: inputs.amount.value, paid_amount: inputs.paid_amount.value });
        });
        inputs[key] = input;
        field.append(input); fields.append(field);
      }
      block.append(fields);
      const actions = this._node("div", undefined, "actions");
      actions.append(this._node("span", row ? `Zbývá ${(row.amount - paid).toLocaleString("cs-CZ")} Kč` : "Částka není určená", "remaining"));
      const data = (confirm) => {
        const amount = Number(inputs.amount.value);
        const paidAmount = inputs.paid_amount.value === "" ? 0 : Number(inputs.paid_amount.value);
        if (inputs.amount.value === "" || !Number.isFinite(amount) || amount < 0 ||
          !Number.isFinite(paidAmount) || paidAmount < 0 || (!confirm && paidAmount > amount)) {
          this._error = "Zadejte zálohu a zaplacenou část mezi nulou a celkovou zálohou.";
          this._render();
          return null;
        }
        return { month, amount, ...(confirm ? { confirm: true } : { paid_amount: paidAmount }), use_monthly: useMonthly.checked };
      };
      const save = this._node("button", "Uložit");
      save.addEventListener("click", () => { const d = data(false); if (d) this._call("update_advance", d, month); });
      const confirm = this._node("button", "Potvrdit", "confirm");
      confirm.addEventListener("click", () => { const d = data(true); if (d) this._call("update_advance", d, month); });
      actions.append(save, confirm);
      block.append(actions); card.append(block);
      if (++m > 12) { m = 1; year++; }
    }
    if (this._error) card.append(this._node("div", this._error, "error"));
    else if (this._notice) card.append(this._node("div", this._notice, "notice"));
    card.append(this._node("p", "Jde o evidenci záloh, bez ověřování bankovních plateb. Nezadaný měsíc není nulová záloha."));
  }
}

if (!customElements.get("cez-advances-card")) customElements.define("cez-advances-card", CezAdvancesCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "cez-advances-card")) window.customCards.push({
  type: "cez-advances-card", name: "ČEZ zálohy", description: "Měsíční zálohy, částečné úhrady a automatické potvrzení.",
});
