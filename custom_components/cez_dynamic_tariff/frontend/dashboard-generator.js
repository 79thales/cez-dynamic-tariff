/* Uses the signed-in administrator's HA connection. No tokens or external assets. */
function cezSameConfig(left, right) {
  const canonical = value => Array.isArray(value) ? value.map(canonical)
    : value && typeof value === "object"
      ? Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]))
      : value;
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));
}

function reuseCurrentCezViews(generated, current) {
  // Keep the user's existing composition and local invoice comparison exactly
  // as edited. Fresh installations use the bundled, customer-free template.
  const base = "cez-dynamic-tariff";
  const main = current?.views?.find(view => view.path === base);
  if (!main) return generated;
  const path = generated.views[0].path;
  const suffixes = ["", "-detaily", "-zalohy"];
  const views = generated.views.map((fallback, index) => {
    const source = current.views.find(view => view.path === base + suffixes[index]);
    if (!source) return fallback;
    const cloned = JSON.parse(JSON.stringify(source).replaceAll(`/lovelace/${base}`, `/lovelace/${path}`));
    cloned.path = path + suffixes[index];
    cloned.subview = index > 0;
    if (!index) cloned.title = generated.views[0].title;
    return cloned;
  });
  return { views };
}

async function appendCezViews(callWS, config) {
  const views = config?.views;
  if (!Array.isArray(views) || views.length !== 3
      || views.some(view => !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(view.path))
      || new Set(views.map(view => view.path)).size !== views.length
      || views[0].subview || !views[1].subview || !views[2].subview) {
    throw new Error("invalid_views");
  }
  const panels = await callWS({ type: "get_panels" });
  if (panels.lovelace?.config?.mode === "yaml") throw new Error("yaml_dashboard");
  let current;
  try { current = await callWS({ type: "lovelace/config" }); }
  catch { throw new Error("overview_not_editable"); }
  if (!Array.isArray(current?.views)) throw new Error("overview_not_editable");
  const collision = views.find(view => current.views.some(existing => existing.path === view.path));
  if (collision) {
    const error = new Error("view_exists"); error.view_path = collision.path; throw error;
  }
  const merged = { ...current, views: [...current.views, ...views] };
  // Recheck after the async read. Refuse to save a stale configuration.
  const latest = await callWS({ type: "lovelace/config" });
  if (!cezSameConfig(current, latest)) throw new Error("overview_changed");
  try { await callWS({ type: "lovelace/config/save", config: merged }); }
  catch {
    // A disconnected response does not prove the save failed. Never roll back
    // or delete views: that could discard an edit the user made in the meantime.
    try {
      const saved = await callWS({ type: "lovelace/config" });
      if (cezSameConfig(saved, merged)) return { view_path: views[0].path };
    } catch { /* report an unconfirmed save */ }
    throw new Error("save_unconfirmed");
  }
  return { view_path: views[0].path };
}

class CezDashboardGenerator extends HTMLElement {
  constructor() {
    super(); this.attachShadow({ mode: "open" }); this._busy = false;
  }
  set hass(value) {
    this._hass = value;
    if (this.isConnected && !this._initialized) this._initialize();
    const menu = this.shadowRoot.querySelector("ha-menu-button"); if (menu) menu.hass = value;
  }
  set narrow(value) { this._narrow = value; }
  connectedCallback() { if (this._hass && !this._initialized) this._initialize(); }
  _get(id) { return this.shadowRoot.getElementById(id); }
  _initialize() {
    this._initialized = true;
    this._cs = (this._hass.language || "cs").startsWith("cs");
    const t = (cs, en) => this._cs ? cs : en;
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;height:100%;overflow:auto;color:var(--primary-text-color);background:var(--primary-background-color);font-family:Roboto,Arial,sans-serif}
      header{display:flex;align-items:center;gap:12px;padding:12px 16px;background:var(--app-header-background-color,var(--primary-color));color:var(--app-header-text-color,#fff)}
      h1{font-size:20px;margin:0}main{max-width:900px;margin:auto;padding:20px}.card{padding:20px;margin-bottom:20px;border:1px solid var(--divider-color);border-radius:16px;background:var(--card-background-color,#fff)}
      .fields{display:grid;grid-template-columns:1fr 1fr;gap:16px}label{display:flex;flex-direction:column;gap:6px}input,textarea{box-sizing:border-box;width:100%;padding:12px;font:inherit;border:1px solid var(--divider-color,#aaa);border-radius:8px;background:var(--card-background-color,#fff);color:var(--primary-text-color)}
      textarea{min-height:250px;font-family:monospace;font-size:12px}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:16px}button{padding:12px 18px;border:0;border-radius:10px;color:var(--text-primary-color,#fff);background:var(--primary-color,#03a9f4);font:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}a{color:var(--primary-color,#0288d1)}p{line-height:1.5}[hidden]{display:none!important}
      @media(max-width:600px){main{padding:12px}.fields{grid-template-columns:1fr}}
    </style><header><ha-menu-button></ha-menu-button><h1>ČEZ – Generate dashboard</h1></header>
    <main><a href="/config/integrations/integration/cez_dynamic_tariff">${t("Zpět do integrace","Back to integration")}</a>
    <div class="card"><h2>${t("Vygenerovat současný přehled","Generate the current overview")}</h2>
      <p>${t("Stejné složení hlavní stránky, detailů a pomocného editoru záloh. Hlavní pohled se přidá do horní lišty Overview (/lovelace).","The current main view, details and auxiliary advances editor. Adds the main view to the top tab bar of Overview (/lovelace).")}</p>
      <div class="fields"><label>${t("Název v horní liště","Top tab title")}<input id="title" maxlength="120" value="ČEZ – cena a vyúčtování"></label>
      <label>${t("Adresa pohledu","View path")}<input id="path" maxlength="60" value="cez-dynamic-tariff" spellcheck="false"></label></div>
      <p>${t("Grafy vyžadují ApexCharts Card (stejně jako současný dashboard). Generátor ji neinstaluje. Chybějící senzory se označí; nejsou nulová spotřeba.","Charts require ApexCharts Card, as in the current dashboard. It is not installed by the generator. Missing sensors are flagged; they do not represent zero consumption.")}</p>
      <button id="preview" disabled>${t("Generate dashboard · náhled","Generate dashboard · preview")}</button>
    </div><div class="card" id="result" hidden><h2>${t("Připravené pohledy","Prepared views")}</h2>
      <p>${t("Hlavní přehled · Detaily · Pomocný editor záloh. Existující pohledy se zachovají.","Main overview · Details · Auxiliary advances editor. Existing views are preserved.")}</p>
      <p id="warning" hidden></p><label>${t("YAML tří pohledů (views)","YAML for three views")}<textarea id="yaml" readonly spellcheck="false"></textarea></label>
      <div class="actions"><button id="create">${t("Přidat do horní lišty","Add to the top tab bar")}</button><button id="copy">${t("Kopírovat YAML","Copy YAML")}</button><button id="download">${t("Stáhnout YAML","Download YAML")}</button></div>
    </div><div class="card" id="status-box" hidden><p id="status" role="status" aria-live="polite"></p><a id="open" hidden>${t("Otevřít pohled","Open view")}</a></div></main>`;
    const menu = this.shadowRoot.querySelector("ha-menu-button"); menu.hass = this._hass; menu.narrow = this._narrow;
    for (const id of ["title", "path"]) this._get(id).addEventListener("input", () => {
      this._preview = null; this._get("result").hidden = true;
    });
    this._get("preview").addEventListener("click", () => this._generate());
    this._get("create").addEventListener("click", () => this._create());
    this._get("copy").addEventListener("click", () => this._copy());
    this._get("download").addEventListener("click", () => this._download());
    this._loadEntry();
  }
  _status(message, path = null) {
    this._get("status-box").hidden = false; this._get("status").textContent = message;
    this._get("open").hidden = !path;
    if (path) this._get("open").href = `/lovelace/${encodeURIComponent(path)}`;
  }
  _setBusy(value) {
    this._busy = value;
    for (const id of ["title", "path", "preview", "create"]) this._get(id).disabled = value;
  }
  async _loadEntry() {
    if (!this._hass.user?.is_admin) {
      this._status(this._cs ? "Generátor je dostupný pouze správci HA." : "The generator requires an HA administrator."); return;
    }
    try {
      const entries = await this._hass.callWS({ type: "cez_dynamic_tariff/dashboard/entries" });
      const selected = new URLSearchParams(window.location.search).get("entry_id");
      this._entryId = entries.find(entry => entry.entry_id === selected)?.entry_id
        || (entries.length === 1 ? entries[0].entry_id : null);
      if (!this._entryId) throw new Error("entry_not_found");
      this._get("preview").disabled = false;
    } catch { this._status(this._cs ? "Integrace ČEZ není dostupná." : "The ČEZ integration is unavailable."); }
  }
  async _generate() {
    if (this._busy || !this._entryId) return;
    this._setBusy(true); this._preview = null; this._get("result").hidden = true;
    try {
      const result = await this._hass.callWS({type:"cez_dynamic_tariff/dashboard/preview",entry_id:this._entryId,
        title:this._get("title").value.trim(),view_path:this._get("path").value.trim()});
      try {
        const current = await this._hass.callWS({ type: "lovelace/config" });
        const config = reuseCurrentCezViews(result.config, current);
        if (config !== result.config) {
          result.config = config;
          // JSON is valid YAML too; no extra parser or network resource needed.
          result.yaml = JSON.stringify(config, null, 2);
        }
      } catch { /* No manual Overview: use the bundled template for export. */ }
      this._preview = result; this._get("yaml").value = result.yaml;
      const missing = [...result.missing_entities, ...result.missing_hdo_sources];
      this._get("warning").hidden = !missing.length;
      this._get("warning").textContent = `${this._cs ? "Zatím nedostupné entity:" : "Currently unavailable entities:"} ${missing.join(", ")}`;
      this._get("result").hidden = false;
      this._status(this._cs ? "Náhled připraven. Do dashboardu se zatím nic nezapsalo." : "Preview ready. No dashboard changes have been saved.");
    } catch { this._status(this._cs ? "Náhled se nepodařilo vytvořit. Ověřte název, adresu a připojení." : "Preview failed. Check the title, path and connection."); }
    finally { this._setBusy(false); }
  }
  async _create() {
    if (this._busy || !this._preview) return;
    this._setBusy(true);
    try {
      const result = await appendCezViews(message => this._hass.callWS(message), this._preview.config);
      this._status(this._cs ? "Přehled byl přidán do horní lišty Overview." : "The view was added to Overview's top tab bar.", result.view_path);
    } catch (error) {
      const messages = {
        view_exists: ["Pohled s touto adresou už existuje. Nevytváří se další kopie. Můžete jej otevřít nebo zadat jinou adresu.", "A view with this path already exists. No duplicate was created. Open it or choose another path."],
        yaml_dashboard: ["Overview je spravovaný v YAML. Vložte vygenerované views do jeho konfigurace ručně.", "Overview is managed in YAML. Add the generated views to its configuration manually."],
        overview_not_editable: ["Overview nemá ručně spravovanou konfiguraci. Nejdříve jej převezměte do ruční správy v HA.", "Overview has no manually managed configuration. Take control of it in HA first."],
        overview_changed: ["Dashboard se mezitím změnil. Klikněte znovu na přidání; nové změny se zachovají.", "The dashboard changed in the meantime. Retry adding the view; existing edits will be preserved."],
        save_unconfirmed: ["Uložení není potvrzené. Ověřte horní lištu; YAML můžete stáhnout. Žádný pohled se nemaže.", "The save is unconfirmed. Check the top tab bar; YAML can be downloaded. No views are deleted."],
      };
      this._status(messages[error.message]?.[this._cs ? 0 : 1] || (this._cs ? "Pohled se nepodařilo přidat." : "The view could not be added."), error.view_path);
    } finally { this._setBusy(false); }
  }
  async _copy() {
    try { await navigator.clipboard.writeText(this._get("yaml").value); }
    catch { this._get("yaml").focus(); this._get("yaml").select(); }
  }
  _download() {
    if (!this._preview) return;
    const url = URL.createObjectURL(new Blob([this._get("yaml").value], {type:"application/yaml;charset=utf-8"}));
    const link = document.createElement("a"); link.href = url; link.download = "cez-dashboard-views.yaml"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
if (!customElements.get("cez-dynamic-tariff-dashboard-generator")) {
  customElements.define("cez-dynamic-tariff-dashboard-generator", CezDashboardGenerator);
}
