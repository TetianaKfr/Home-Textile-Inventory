const state = {
  token: localStorage.getItem("hti_token") || "",
  familyId: localStorage.getItem("hti_family") || "",
  user: null,
  memberships: [],
  meta: null,
  offline: false,
};

const appEl = document.getElementById("app");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));
}

function photoUrl(id, size = "thumb") {
  const params = new URLSearchParams({ size, access_token: state.token });
  if (state.familyId) params.set("family_id", state.familyId);
  return `/api/photos/${id}/file?${params.toString()}`;
}

function homePhotoUrl(id, size = "thumb") {
  const params = new URLSearchParams({ size, access_token: state.token });
  if (state.familyId) params.set("family_id", state.familyId);
  return `/api/homes/${id}/photo?${params.toString()}`;
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (state.familyId) headers["X-Family-Id"] = state.familyId;
  let body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, { ...options, headers, body });
    state.offline = false;
  } catch (error) {
    state.offline = true;
    throw new Error("You are offline. Showing the last inventory that was saved on this device.");
  }
  const text = await response.text();
  let data = null;
  if (text) {
    try { data = JSON.parse(text); } catch { data = text; }
  }
  if (!response.ok) {
    const error = new Error("Request failed");
    error.status = response.status;
    error.detail = data && data.detail ? data.detail : data;
    throw error;
  }
  return data;
}

function role() {
  const membership = state.memberships.find((item) => String(item.family_id) === String(state.familyId)) || state.memberships[0];
  return membership ? membership.role : "viewer";
}

function canEdit() { return role() === "admin" || role() === "editor"; }
function canAdmin() { return role() === "admin"; }

function route() {
  const hash = location.hash || "#/dashboard";
  const [path, query] = hash.slice(1).split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(query || "");
  return { parts, params };
}

function go(hash) {
  location.hash = hash;
}

async function boot() {
  if (!state.token && !route().parts.includes("login") && route().parts[0] !== "register") {
    if (route().parts[0] !== "accept") go("#/login");
  }
  if (state.token && !state.user) {
    try {
      const me = await api("/api/auth/me");
      state.user = me.user;
      state.memberships = me.memberships;
      if (!state.familyId && me.memberships[0]) state.familyId = String(me.memberships[0].family_id);
      state.meta = await api("/api/meta");
    } catch (error) {
      if (error.status === 401) {
        state.token = "";
        localStorage.removeItem("hti_token");
        go("#/login");
      }
    }
  }
  await render();
}

function shell(content) {
  const links = [
    ["#/dashboard", "Dashboard"],
    ["#/inventory", "Inventory"],
    ["#/items/new", "Add item"],
    ["#/match", "AI matching"],
    ["#/locations", "Storage"],
    ["#/objects", "Beds, tables, windows"],
    ["#/sets", "Saved sets"],
    ["#/family", "Family"],
    ["#/settings", "Settings"],
  ];
  const current = "#" + (location.hash.slice(1).split("?")[0] || "/dashboard");
  return `
    <div class="shell">
      <aside class="nav">
        <h1 class="brand">Home Textile<span>Shared inventory</span></h1>
        ${links.map(([href, label]) => `<a class="${current.startsWith(href) ? "active" : ""}" href="${href}">${label}</a>`).join("")}
        <div class="spacer"></div>
        <div class="small">${esc(state.user ? state.user.full_name : "")}<br>${esc(role())}</div>
        <button class="link" id="logout">Sign out</button>
      </aside>
      <main class="main">
        ${state.offline ? `<div class="banner">Offline. Recently loaded inventory is still available on this device.</div>` : ""}
        ${content}
      </main>
    </div>`;
}

function field(label, html) {
  return `<label>${esc(label)}${html}</label>`;
}

async function render() {
  const { parts } = route();
  try {
    if (parts[0] === "login" || !state.token && parts[0] !== "register" && parts[0] !== "accept") {
      appEl.innerHTML = authView(false);
      bindAuth(false);
      return;
    }
    if (parts[0] === "register") {
      appEl.innerHTML = authView(true);
      bindAuth(true);
      return;
    }
    if (parts[0] === "accept") {
      appEl.innerHTML = shell(`<section class="panel"><h1>Invitation</h1><p id="invite-box">Checking the invitation…</p></section>`);
      bindLogout();
      await renderAccept(parts[1]);
      return;
    }
    if (parts[0] === "search") {
      const query = location.hash.includes("?") ? "?" + location.hash.split("?")[1] : "";
      go("#/inventory" + query);
      return;
    }
    if (parts[0] === "dashboard") appEl.innerHTML = shell(await dashboardView());
    else if (parts[0] === "inventory") appEl.innerHTML = shell(await inventoryView());
    else if (parts[0] === "items" && parts[1] === "new") appEl.innerHTML = shell(await itemFormView(null));
    else if (parts[0] === "items" && parts[2] === "edit") appEl.innerHTML = shell(await itemFormView(parts[1]));
    else if (parts[0] === "items" && parts[1]) appEl.innerHTML = shell(await itemDetailView(parts[1]));
    else if (parts[0] === "locations" && parts[1]) appEl.innerHTML = shell(await locationDetailView(parts[1]));
    else if (parts[0] === "locations") appEl.innerHTML = shell(await locationsView());
    else if (parts[0] === "objects" && parts[1] === "new") appEl.innerHTML = shell(await objectFormView());
    else if (parts[0] === "objects" && parts[2] === "edit") appEl.innerHTML = shell(await objectFormView(parts[1]));
    else if (parts[0] === "objects" && parts[1] === "home" && parts[2]) appEl.innerHTML = shell(await objectsHomeView(parts[2]));
    else if (parts[0] === "objects") appEl.innerHTML = shell(await objectsView());
    else if (parts[0] === "match") appEl.innerHTML = shell(await matchView());
    else if (parts[0] === "sets") appEl.innerHTML = shell(await setsView());
    else if (parts[0] === "family") appEl.innerHTML = shell(await familyView());
    else if (parts[0] === "settings") appEl.innerHTML = shell(await settingsView());
    else appEl.innerHTML = shell(await dashboardView());
    bindLogout();
    bindPage(parts);
  } catch (error) {
    appEl.innerHTML = shell(`<section class="panel"><h1>Something needs attention</h1><p>${esc(messageOf(error))}</p></section>`);
    bindLogout();
  }
}

function messageOf(error) {
  if (!error) return "Unknown error";
  if (typeof error.detail === "string") return error.detail;
  if (error.detail && error.detail.message) return error.detail.message;
  return error.message || "Request failed";
}

function authView(registering) {
  return `<section class="panel auth">
    <h1>${registering ? "Create a household" : "Sign in"}</h1>
    <p class="muted">${registering ? "You become the administrator of a new family group." : "One shared inventory for the whole household."}</p>
    ${registering ? "" : `<div class="banner">Demo accounts use the password <b>Demo1234!</b><br>demo@home-textile.local (admin), editor@home-textile.local, viewer@home-textile.local</div>`}
    <form id="auth-form" class="filters">
      ${registering ? field("Your name", `<input name="full_name" required>`) : ""}
      ${registering ? field("Family group", `<input name="family_name" required>`) : ""}
      ${field("Email", `<input name="email" type="email" required>`)}
      ${field("Password", `<input name="password" type="password" minlength="8" required>`)}
      <button class="btn" type="submit">${registering ? "Create account" : "Sign in"}</button>
    </form>
    <p>${registering ? `<a href="#/login">I already have an account</a>` : `<a href="#/register">Create a family group</a>`}</p>
    <p id="auth-error" class="error banner" hidden></p>
  </section>`;
}

function bindAuth(registering) {
  document.getElementById("auth-form").onsubmit = async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target).entries());
    const box = document.getElementById("auth-error");
    try {
      const path = registering ? "/api/auth/register" : "/api/auth/login";
      const result = await api(path, { method: "POST", body: data });
      state.token = result.access_token;
      state.user = result.user;
      state.memberships = result.memberships;
      state.familyId = result.memberships[0] ? String(result.memberships[0].family_id) : "";
      localStorage.setItem("hti_token", state.token);
      localStorage.setItem("hti_family", state.familyId);
      state.meta = await api("/api/meta");
      go("#/dashboard");
    } catch (error) {
      box.hidden = false;
      box.textContent = messageOf(error);
    }
  };
}

function bindLogout() {
  const button = document.getElementById("logout");
  if (!button) return;
  button.onclick = () => {
    state.token = "";
    state.user = null;
    localStorage.removeItem("hti_token");
    go("#/login");
  };
}

async function dashboardView() {
  const data = await api("/api/dashboard");
  const statuses = Object.entries(data.by_status).map(([name, count]) => `<span class="pill ${esc(name)}">${esc(name.replaceAll("_", " "))} ${count}</span>`).join(" ");
  return `<div class="top"><h1>Dashboard</h1></div>
    <div class="stats">
      <article class="panel stat"><b>${data.item_count}</b><span class="muted">items</span></article>
      <article class="panel stat"><b>${data.unit_count}</b><span class="muted">physical units</span></article>
    </div>
    <section class="panel" style="margin-bottom:14px"><h2>Where things are</h2><p>${statuses || "No units yet."}</p>
      <p>${data.by_category.map((row) => `${esc(row.name)} (${row.count})`).join(" · ") || ""}</p>
    </section>
    <h2>Recently added</h2>
    ${cards(data.recent_items)}`;
}

function placeLabel(unit) {
  if (!unit || unit.location_id == null) return unit && unit.location_path ? unit.location_path : "No location";
  if (unit.home_name || unit.room_name || unit.location_name) {
    return [unit.home_name, unit.room_name, unit.location_name].filter(Boolean).join(" / ");
  }
  return unit.location_path || "No location";
}

function placeDetails(unit) {
  if (!unit || unit.location_id == null) return `<p>No location</p>`;
  return `<p>Home: ${esc(unit.home_name || "—")}</p>
    <p>Room: ${esc(unit.room_name || "—")}</p>
    <p>Inside: ${esc(unit.inside || "—")}</p>
    <p>Type: ${esc(unit.location_type || "—")}</p>`;
}

function cards(items) {
  if (!items.length) return `<p class="muted">Nothing here yet.</p>`;
  return `<div class="grid">${items.map((item) => {
    const photo = item.photos && item.photos[0];
    const place = item.units && item.units[0] ? placeLabel(item.units[0]) : "No location";
    const status = item.units && item.units[0] ? item.units[0].status : "";
    return `<a class="card" href="#/items/${item.id}">
      ${photo ? `<img src="${photoUrl(photo.id)}" alt="">` : `<div class="ph">No photo</div>`}
      <div class="body">
        <strong>${esc(item.name)}</strong>
        <div class="small muted">${esc(item.category ? item.category.name : "")}</div>
        <div class="small">${esc(item.dimensions_label)} · ${esc(item.primary_color || "color unknown")}</div>
        <div class="row"><span class="pill ${esc(status)}">${esc((status || "no status").replaceAll("_", " "))}</span><span class="small">${esc(place)}</span></div>
      </div>
    </a>`;
  }).join("")}</div>`;
}

function parseSize(text) {
  const match = String(text || "").trim().match(/^(\d+(?:[.,]\d+)?)\s*(?:x|×|\/|by|на)\s*(\d+(?:[.,]\d+)?)$/i);
  if (!match) return null;
  return [Number(match[1].replace(",", ".")), Number(match[2].replace(",", "."))];
}

async function inventoryView() {
  const [categories, tree] = await Promise.all([
    api("/api/categories"),
    api("/api/locations/tree"),
  ]);
  const homes = tree.homes || [];
  const params = route().params;
  const sizeText = params.get("size") || "";
  const sizeError = sizeText && !parseSize(sizeText)
    ? "Could not read that size. Use width × length, for example 220 × 200."
    : "";
  const query = new URLSearchParams();
  ["q", "category_id", "color", "material", "pattern", "status", "seasonality", "sort", "size", "home_id"].forEach((key) => {
    if (params.get(key)) query.set(key, params.get(key));
  });
  if (sizeError) query.delete("size");
  let items = [];
  try {
    items = await api("/api/items?" + query.toString());
    localStorage.setItem("hti_items", JSON.stringify(items));
  } catch (error) {
    if (state.offline) items = JSON.parse(localStorage.getItem("hti_items") || "[]");
    else throw error;
  }
  const options = (list) => list.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
  return `<div class="top"><h1>Inventory</h1>${canEdit() ? `<a class="btn" href="#/items/new">Add item</a>` : ""}</div>
    <form id="filters" class="filters">
      ${field("Search", `<input name="q" value="${esc(params.get("q") || "")}" placeholder="white pillowcase, box 4, cotton">`)}
      ${field("Size", `<input name="size" value="${esc(sizeText)}" placeholder="220 × 200" inputmode="decimal">`)}
      ${field("House", `<select name="home_id"><option value="">Any</option>${homes.map((home) => `<option value="${home.id}" ${params.get("home_id") == home.id ? "selected" : ""}>${esc(home.name)}</option>`).join("")}</select>`)}
      ${field("Category", `<select name="category_id"><option value="">Any</option>${categories.map((c) => `<option value="${c.id}" ${params.get("category_id") == c.id ? "selected" : ""}>${esc(c.group_name)} — ${esc(c.name)}</option>`).join("")}</select>`)}
      ${field("Color", `<input name="color" list="colors" value="${esc(params.get("color") || "")}">`)}
      ${field("Material", `<input name="material" list="materials" value="${esc(params.get("material") || "")}">`)}
      ${field("Pattern", `<input name="pattern" list="patterns" value="${esc(params.get("pattern") || "")}">`)}
      ${field("Status", `<select name="status"><option value="">Any</option>${state.meta.statuses.map((s) => `<option ${params.get("status") === s ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>`)}
      ${field("Sort", `<select name="sort">
        ${["name", "category", "width", "created", "location"].map((s) => `<option ${params.get("sort") === s ? "selected" : ""}>${s}</option>`).join("")}
      </select>`)}
      <button class="btn" type="submit">Apply</button>
      ${sizeError ? `<p class="banner error">${esc(sizeError)}</p>` : ""}
    </form>
    <datalist id="colors">${options(state.meta.colors)}</datalist>
    <datalist id="materials">${options(state.meta.materials)}</datalist>
    <datalist id="patterns">${options(state.meta.patterns)}</datalist>
    <p class="muted">${items.length} item${items.length === 1 ? "" : "s"}</p>
    ${cards(items)}`;
}

async function itemDetailView(id) {
  const item = await api("/api/items/" + id);
  const history = await api(`/api/items/${id}/history`);
  const sources = item.field_sources || {};
  const sourceNote = (key) => sources[key] === "ai" ? ` <span class="pill possible">AI suggestion, unconfirmed</span>` : "";
  return `<div class="top"><div><h1>${esc(item.name)}</h1><p class="muted">${esc(item.category ? item.category.name : "")}</p></div>
    <div class="row">${canEdit() ? `<a class="btn" href="#/items/${item.id}/edit">Edit</a>` : ""}</div></div>
    <div class="split">
      <section>
        <div class="gallery">${item.photos.map((photo) => `<img src="${photoUrl(photo.id, "full")}" alt="">`).join("") || `<div class="ph">No photograph</div>`}</div>
        <section class="panel" style="margin-top:12px">
          <p>${esc(item.dimensions_label)} ${sourceNote("width")}</p>
          <p>Color: ${esc(item.primary_color || "unknown")}${sourceNote("primary_color")} ${item.secondary_colors.length ? "· also " + esc(item.secondary_colors.join(", ")) : ""}</p>
          <p>Pattern: ${esc(item.pattern || "unknown")}${sourceNote("pattern")} · Material: ${esc(item.material || "unknown")}${sourceNote("material")}</p>
          <p>Brand: ${esc(item.brand || "—")} · Season: ${esc(item.seasonality || "—")}</p>
          <p>${esc(item.description || item.notes || "")}</p>
          ${Object.entries(item.attributes || {}).map(([key, value]) => `<p>${esc(key.replaceAll("_", " "))}: ${esc(value)}</p>`).join("")}
        </section>
      </section>
      <aside>
        <section class="panel">
          <h2>Physical units</h2>
          ${item.units.map((unit) => `<div style="margin-bottom:10px"><span class="pill ${esc(unit.status)}">${esc(unit.status.replaceAll("_", " "))}</span>${placeDetails(unit)}</div>`).join("") || "<p>No units.</p>"}
          <p class="small muted">Quantity ${item.quantity}. Version ${item.version}.</p>
        </section>
        <section class="panel" style="margin-top:12px">
          <h2>History</h2>
          ${history.slice(0, 8).map((row) => `<p class="small">${esc(row.created_at || "").replace("T", " ").slice(0, 16)} · ${esc(row.user_name)} · ${esc(row.action.replaceAll("_", " "))}</p>`).join("") || "<p>No history yet.</p>"}
        </section>
      </aside>
    </div>`;
}

async function itemFormView(id) {
  const [categories, tree, existing] = await Promise.all([
    api("/api/categories"),
    api("/api/locations/tree"),
    id ? api("/api/items/" + id) : Promise.resolve(null),
  ]);
  const locations = flattenLocations(tree);
  const selected = existing ? existing.category.id : "";
  window.__formCache = { categories, locations, existing };
  return `<div class="top"><h1>${existing ? "Edit item" : "Add item"}</h1></div>
    <form id="item-form" class="panel filters">
      ${canEdit() && !existing ? `<div class="banner">AI can estimate color from a photograph. It will leave measurements, material, and brand empty.</div>
        ${field("Photograph for suggestions", `<input id="ai-file" type="file" accept="image/*">`)}
        <button class="btn secondary" id="ai-btn" type="button">Suggest from photograph</button>
        <p id="ai-note" class="small"></p>` : ""}
      ${field("Category", `<select name="category_id" id="category" required>${categories.map((c) => `<option value="${c.id}" ${String(selected) === String(c.id) ? "selected" : ""}>${esc(c.group_name)} — ${esc(c.name)}</option>`).join("")}</select>`)}
      ${field("Name", `<input name="name" required value="${esc(existing ? existing.name : "")}">`)}
      ${locationFields(existing)}
      ${field("Dimensions", `<input name="dimension_text" placeholder="140 × 190" value="${existing && existing.width && existing.length ? `${existing.width} x ${existing.length}` : ""}">`)}
      <div id="extra-fields" class="filters"></div>
      ${field("Primary color", `<input name="primary_color" list="colors" value="${esc(existing ? existing.primary_color : "")}">`)}
      ${field("Other colors", `<input name="secondary_colors" value="${esc(existing ? (existing.secondary_colors || []).join(", ") : "")}">`)}
      ${field("Pattern", `<input name="pattern" list="patterns" value="${esc(existing ? existing.pattern : "")}">`)}
      ${field("Material", `<input name="material" list="materials" value="${esc(existing ? existing.material : "")}">`)}
      ${field("Texture", `<input name="texture" value="${esc(existing ? existing.texture : "")}">`)}
      ${field("Brand", `<input name="brand" value="${esc(existing ? existing.brand : "")}">`)}
      ${field("Season", `<input name="seasonality" list="seasons" value="${esc(existing ? existing.seasonality : "")}">`)}
      ${field("Description", `<textarea name="description">${esc(existing ? existing.description : "")}</textarea>`)}
      ${field("Notes", `<textarea name="notes">${esc(existing ? existing.notes : "")}</textarea>`)}
      ${existing ? "" : field("Quantity", `<input name="quantity" type="number" min="1" value="1">`)}
      ${existing ? "" : field("Status", `<select name="unit_status">${state.meta.statuses.map((s) => `<option>${esc(s)}</option>`).join("")}</select>`)}
      <input type="hidden" name="version" value="${existing ? existing.version : 1}">
      <button class="btn" type="submit">${existing ? "Save changes" : "Save item"}</button>
      <p id="form-error" class="banner error" hidden></p>
      <div id="dupes"></div>
    </form>
    <datalist id="colors">${state.meta.colors.map((v) => `<option value="${esc(v)}">`).join("")}</datalist>
    <datalist id="patterns">${state.meta.patterns.map((v) => `<option value="${esc(v)}">`).join("")}</datalist>
    <datalist id="materials">${state.meta.materials.map((v) => `<option value="${esc(v)}">`).join("")}</datalist>
    <datalist id="seasons">${state.meta.seasons.map((v) => `<option value="${esc(v)}">`).join("")}</datalist>`;
}

function locationOptions(selectedId) {
  const locations = (window.__formCache && window.__formCache.locations) || [];
  const selected = selectedId == null ? "" : String(selectedId);
  return `<option value="">No location yet</option>${locations.map((loc) => `<option value="${loc.id}" ${String(loc.id) === selected ? "selected" : ""}>${esc(loc.label)}</option>`).join("")}`;
}

function locationFields(existing) {
  const units = existing && existing.units ? existing.units : [];
  if (!existing || units.length === 0) {
    return field("Location", `<select name="location_id">${locationOptions("")}</select>`);
  }
  if (units.length === 1) {
    return field("Location", `<select name="unit_location_${units[0].id}">${locationOptions(units[0].location_id)}</select>`);
  }
  return units.map((unit, index) => field(`Unit ${index + 1} location`, `<select name="unit_location_${unit.id}">${locationOptions(unit.location_id)}</select>`)).join("");
}

function flattenLocations(tree) {
  const options = [];
  for (const home of tree.homes || []) {
    for (const room of home.rooms || []) walk(room.locations || [], `${home.name} / ${room.name}`);
  }
  function walk(nodes, prefix) {
    for (const node of nodes) {
      options.push({ id: node.id, label: `${prefix} / ${node.name}` });
      walk(node.children || [], `${prefix} / ${node.name}`);
    }
  }
  return options;
}

function renderExtraFields() {
  const cache = window.__formCache;
  if (!cache) return;
  const select = document.getElementById("category");
  const category = cache.categories.find((item) => String(item.id) === select.value);
  const box = document.getElementById("extra-fields");
  if (!category || !box) return;
  const schema = category.attribute_schema || { dimensions: [], fields: [] };
  const existing = cache.existing;
  const dims = (schema.dimensions || []).filter((key) => !["width", "length"].includes(key));
  const dimensionInputs = dims.map((key) => field(key.replaceAll("_", " "), `<input name="dim_${key}" type="number" step="0.1" value="${esc(existing && existing[key] != null ? existing[key] : (existing && existing.attributes[key] != null ? existing.attributes[key] : ""))}">`));
  const extras = (schema.fields || []).map((spec) => {
    const value = existing && existing.attributes ? existing.attributes[spec.key] || "" : "";
    if (spec.type === "select") {
      return field(spec.label, `<input name="attr_${spec.key}" list="list-${spec.key}" value="${esc(value)}"><datalist id="list-${spec.key}">${(spec.options || []).map((opt) => `<option value="${esc(opt)}">`).join("")}</datalist>`);
    }
    const type = spec.type === "number" ? "number" : "text";
    return field(spec.label + (spec.unit ? ` (${spec.unit})` : ""), `<input name="attr_${spec.key}" type="${type}" step="0.1" value="${esc(value)}">`);
  });
  box.innerHTML = dimensionInputs.concat(extras).join("");
}

function collectItem(form, acknowledge) {
  const data = Object.fromEntries(new FormData(form).entries());
  const attributes = {};
  Object.keys(data).forEach((key) => {
    if (key.startsWith("attr_") || key.startsWith("dim_")) {
      if (data[key] !== "") attributes[key.replace(/^attr_|^dim_/, "")] = data[key].match(/^-?\d+(\.\d+)?$/) ? Number(data[key]) : data[key];
    }
  });
  const sources = window.__sources || (window.__formCache.existing && window.__formCache.existing.field_sources) || {};
  ["primary_color", "pattern", "material", "texture"].forEach((key) => {
    const original = window.__formCache.existing ? window.__formCache.existing[key] : "";
    if (sources[key] === "ai" && data[key] !== original && data[key] !== (window.__aiOriginal || {})[key]) sources[key] = "user";
  });
  return {
    category_id: Number(data.category_id),
    name: data.name,
    description: data.description || "",
    brand: data.brand || "",
    primary_color: data.primary_color || "",
    secondary_colors: (data.secondary_colors || "").split(",").map((part) => part.trim()).filter(Boolean),
    pattern: data.pattern || "",
    texture: data.texture || "",
    material: data.material || "",
    seasonality: data.seasonality || "",
    notes: data.notes || "",
    dimension_text: data.dimension_text || null,
    height: attributes.height ?? null,
    diameter: attributes.diameter ?? null,
    attributes,
    field_sources: sources,
    quantity: Number(data.quantity || 1),
    unit_status: data.unit_status || "available",
    location_id: data.location_id ? Number(data.location_id) : null,
    version: Number(data.version || 1),
    acknowledge_duplicates: acknowledge,
  };
}

async function locationsView() {
  const tree = await api("/api/locations/tree");
  window.__placeTree = tree;
  const homes = tree.homes.map(homeSection).join("");
  return `<div class="top"><h1>Homes and storage</h1></div>
    ${canEdit() ? `<form id="place-form" class="panel filters" style="margin-bottom:12px">
      ${field("Add", `<select name="kind"><option value="home">Home</option><option value="room">Room</option><option value="storage">Storage location</option></select>`)}
      ${field("Name", `<input name="name" required placeholder="Xavier, Saint-Malo">`)}
      ${field("Home", `<select name="home_id"></select>`)}
      ${field("Room", `<select name="room_id"></select>`)}
      ${field("Inside", `<select name="parent_id"></select>`)}
      ${field("Type", `<select name="location_type"><option value="shelf">shelf</option><option value="drawer">drawer</option><option value="box">box</option><option value="cupboard">cupboard</option></select>`)}
      <button class="btn" type="submit" id="place-submit">Add home</button>
      <p id="place-error" class="banner error" hidden></p>
    </form>` : ""}
    <p id="homes-error" class="banner error" hidden></p>
    ${homes || "<p>No homes yet.</p>"}`;
}

function homeSection(home) {
  const rooms = (home.rooms || []).map((room) => roomLine(room, home.id)).join("") || `<p class="muted">No rooms yet.</p>`;
  const actions = canEdit() ? `<div class="row">
      <button class="btn secondary" type="button" data-edit-home="${home.id}">Edit</button>
      ${canAdmin() ? `<button class="btn warn" type="button" data-delete-home="${home.id}" data-home-name="${esc(home.name)}">Delete</button>` : ""}
    </div>` : "";
  const editor = canEdit() ? `<div data-home-editor="${home.id}" hidden>
      <form class="filters" data-home-form="${home.id}">
        ${field("Home name", `<input name="name" required value="${esc(home.name)}">`)}
        <button class="btn" type="submit">Save</button>
        <button class="btn secondary" type="button" data-cancel-home="${home.id}">Cancel</button>
      </form>
      <p class="banner error" data-home-error="${home.id}" hidden></p>
    </div>` : "";
  return `<section class="panel home-card" style="margin-bottom:12px">
    <div class="top"><h2>${esc(home.name)}</h2>${actions}</div>
    ${editor}
    <div class="place-table">${rooms}</div>
  </section>`;
}

function roomLine(room, homeId) {
  const del = canEdit() ? `<button class="btn warn tiny edit-only" type="button" data-delete-room="${room.id}" data-room-name="${esc(room.name)}" data-home-id="${homeId}">Delete</button>` : "";
  return `<div class="place-row">
      <div class="place-label"><h3>${esc(room.name)}</h3></div>
      ${del}
    </div>${renderTree(room.locations, homeId, 1)}`;
}

function renderTree(nodes, homeId, depth) {
  if (!nodes || !nodes.length) return "";
  return nodes.map((node) => `<div class="place-row">
      <div class="place-label" style="padding-left:${depth * 18}px">
        <a href="#/locations/${node.id}">${esc(node.name)}</a>
        <span class="muted small">${esc(node.location_type)}</span>
      </div>
      ${canEdit() ? `<button class="btn warn tiny edit-only" type="button" data-delete-storage="${node.id}" data-storage-name="${esc(node.name)}" data-home-id="${homeId}">Delete</button>` : ""}
    </div>${renderTree(node.children, homeId, depth + 1)}`).join("");
}

async function locationDetailView(id) {
  const data = await api("/api/storage/" + id);
  const isBox = String(data.type || "").toLowerCase() === "box";
  return `<div class="top"><h1>${esc(data.name)}</h1></div>
    <section class="panel"><p>${esc(data.path)}</p><p class="muted">${esc(data.type)}</p>
    ${isBox ? `<img id="qr" alt="QR code for this box" style="width:180px;height:180px;background:#fff">` : ""}
    <h2>Items here</h2>
    ${data.items.map((item) => `<p><a href="#/items/${item.id}">${esc(item.name)}</a> · ${esc(item.category)} · ${item.quantity_here}</p>`).join("") || "<p>This location is empty.</p>"}
    </section>`;
}

function measureInput(name, value) {
  const number = Number(value);
  const shown = value == null || value === "" || !Number.isFinite(number) || number < 0 ? "" : esc(value);
  return `<input name="${name}" type="text" inputmode="decimal" autocomplete="off" data-measure="1" placeholder="type a size, 0 or more" value="${shown}">`;
}

function bindMeasureFields(form) {
  form.querySelectorAll("[data-measure]").forEach((input) => {
    input.addEventListener("input", () => {
      const cleaned = input.value.replace(",", ".").replace(/[^\d.]/g, "");
      const parts = cleaned.split(".");
      const next = parts.length > 1 ? `${parts[0]}.${parts.slice(1).join("")}` : parts[0];
      if (next !== input.value) input.value = next;
    });
  });
}

function objectMeasures(obj) {
  const bits = [];
  const add = (label, value) => {
    const number = Number(value);
    if (value == null || value === "" || !Number.isFinite(number) || number < 0) return;
    const text = Number.isInteger(number) ? String(number) : String(Math.round(number * 10) / 10);
    bits.push(`${label} ${text} cm`);
  };
  add("width", obj.width);
  add("length", obj.length);
  add("height", obj.height);
  add("diameter", obj.diameter);
  add("depth", obj.depth);
  const attrs = obj.attributes || {};
  add("rail", attrs.rail_width);
  add("curtain length", attrs.desired_length);
  if (obj.kind === "bed" && Array.isArray(attrs.pillows)) {
    attrs.pillows.forEach((pillow, index) => {
      if (!pillow || typeof pillow !== "object") return;
      const width = Number(pillow.width);
      const length = Number(pillow.length);
      const hasWidth = pillow.width != null && pillow.width !== "" && Number.isFinite(width) && width >= 0;
      const hasLength = pillow.length != null && pillow.length !== "" && Number.isFinite(length) && length >= 0;
      const text = (number) => (Number.isInteger(number) ? String(number) : String(Math.round(number * 10) / 10));
      if (hasWidth && hasLength) bits.push(`pillow ${index + 1} ${text(width)} × ${text(length)} cm`);
      else if (hasWidth) bits.push(`pillow ${index + 1} width ${text(width)} cm`);
      else if (hasLength) bits.push(`pillow ${index + 1} length ${text(length)} cm`);
    });
  }
  return bits.join(" · ") || "Enter the length and height";
}

function syncObjectPlace() {
  const form = document.getElementById("object-form");
  const tree = window.__objectTree || { homes: [] };
  if (!form || !form.elements.home_id || !form.elements.room_id) return;
  const home = (tree.homes || []).find((item) => String(item.id) === form.elements.home_id.value);
  const rooms = home ? home.rooms || [] : [];
  const selected = form.elements.room_id.value || form.elements.room_id.dataset.selected || "";
  fillSelect(
    form.elements.room_id,
    rooms.map((room) => ({ id: room.id, label: room.name })),
    selected,
    "No room yet",
  );
  form.elements.room_id.dataset.selected = "";
}

function syncObjectKind() {
  const form = document.getElementById("object-form");
  const pillows = form && form.querySelector("[data-bed-pillows]");
  if (!pillows || !form.elements.kind) return;
  pillows.hidden = form.elements.kind.value !== "bed";
}

async function objectFormView(id) {
  let existing = null;
  if (id) {
    const objects = await api("/api/objects");
    existing = objects.find((obj) => String(obj.id) === String(id)) || null;
    if (!existing) return `<div class="top"><h1>Object not found</h1></div>`;
  }
  const tree = await api("/api/locations/tree");
  window.__objectTree = tree;
  const attrs = existing && existing.attributes ? existing.attributes : {};
  const kind = existing ? existing.kind : "bed";
  const kinds = [["bed", "Bed"], ["mattress", "Mattress"], ["table", "Table"], ["window", "Window"]];
  const shapes = [["", ""], ["rectangular", "rectangular"], ["round", "round"], ["oval", "oval"], ["square", "carre"]];
  const shape = existing && existing.shape === "carré" ? "square" : (existing ? existing.shape || "" : "");
  const homeId = existing && existing.home_id != null ? String(existing.home_id) : "";
  const roomId = existing && existing.room_id != null ? String(existing.room_id) : "";
  const homes = tree.homes || [];
  const pillows = Array.isArray(attrs.pillows) ? attrs.pillows : [];
  const pillowFields = [1, 2, 3, 4].map((n) => {
    const pillow = pillows[n - 1] || {};
    return field(`Pillow ${n} width cm`, measureInput(`pillow_${n}_width`, pillow.width))
      + field(`Pillow ${n} length cm`, measureInput(`pillow_${n}_length`, pillow.length));
  }).join("");
  return `<div class="top"><h1>${existing ? "Change length and height" : "Add a household object"}</h1></div>
    <form id="object-form" class="panel filters">
      <p class="muted">Choose the home and the room from the lists. Type the length, height, diameter, mattress depth, curtain rail width and desired curtain length. For a bed, pillow sizes are optional: fill up to 4, or leave every pillow field empty. A negative number cannot be entered.</p>
      ${existing ? `<input type="hidden" name="object_id" value="${existing.id}">` : ""}
      ${field("Type", `<select name="kind">${kinds.map(([value, label]) => `<option value="${value}" ${kind === value ? "selected" : ""}>${label}</option>`).join("")}</select>`)}
      ${field("Name", `<input name="name" required value="${esc(existing ? existing.name : "")}">`)}
      ${field("Home", `<select name="home_id"><option value="">No home yet</option>${homes.map((home) => `<option value="${home.id}" ${String(home.id) === homeId ? "selected" : ""}>${esc(home.name)}</option>`).join("")}</select>`)}
      ${field("Room", `<select name="room_id" data-selected="${esc(roomId)}"></select>`)}
      ${field("Shape", `<select name="shape">${shapes.map(([value, label]) => `<option value="${esc(value)}" ${shape === value ? "selected" : ""}>${esc(label)}</option>`).join("")}</select>`)}
      ${field("Width cm", measureInput("width", existing && existing.width))}
      ${field("Length cm", measureInput("length", existing && existing.length))}
      ${field("Height cm", measureInput("height", existing && existing.height))}
      ${field("Diameter cm", measureInput("diameter", existing && existing.diameter))}
      ${field("Mattress depth cm", measureInput("depth", existing && existing.depth))}
      <div class="bed-pillows" data-bed-pillows ${kind === "bed" ? "" : "hidden"}>
        <p class="muted">Pillow sizes, optional. Width and length in centimetres. Leave a pillow blank if the bed does not need it.</p>
        ${pillowFields}
      </div>
      ${field("Curtain rail width", measureInput("rail_width", attrs.rail_width))}
      ${field("Desired curtain length", measureInput("desired_length", attrs.desired_length))}
      ${field("Fullness ratio", measureInput("fullness", attrs.fullness))}
      ${field("Attachment", `<input name="attachment" placeholder="eyelets" value="${esc(attrs.attachment || "")}">`)}
      ${field("Preferred table overhang cm", measureInput("overhang", attrs.overhang))}
      ${field("Notes", `<textarea name="notes">${esc(existing ? existing.notes : "")}</textarea>`)}
      <button class="btn" type="submit">${existing ? "Save measurements" : "Save object"}</button>
      <p id="object-error" class="banner error" hidden></p>
    </form>`;
}

function comparePlaceName(left, right) {
  const a = left || "";
  const b = right || "";
  if (!a && b) return 1;
  if (a && !b) return -1;
  return a.localeCompare(b, undefined, { sensitivity: "base", numeric: true });
}

function groupObjects(objects) {
  const homes = new Map();
  for (const obj of objects) {
    const homeKey = obj.home_id == null ? "" : String(obj.home_id);
    const roomKey = obj.room_id == null ? "" : String(obj.room_id);
    if (!homes.has(homeKey)) homes.set(homeKey, { name: obj.home_name || "", rooms: new Map() });
    const home = homes.get(homeKey);
    if (!home.name && obj.home_name) home.name = obj.home_name;
    if (!home.rooms.has(roomKey)) home.rooms.set(roomKey, { name: obj.room_name || "", objects: [] });
    const room = home.rooms.get(roomKey);
    if (!room.name && obj.room_name) room.name = obj.room_name;
    room.objects.push(obj);
  }
  return [...homes.values()]
    .sort((a, b) => comparePlaceName(a.name, b.name))
    .map((home) => ({
      name: home.name,
      rooms: [...home.rooms.values()]
        .sort((a, b) => comparePlaceName(a.name, b.name))
        .map((room) => ({
          name: room.name,
          objects: room.objects.slice().sort((a, b) => comparePlaceName(a.name, b.name) || comparePlaceName(a.kind, b.kind)),
        })),
    }));
}

function objectLine(obj) {
  return `<li class="object-line">
      <strong>${esc(obj.name)}</strong>
      <div class="small muted">${esc(obj.kind)} · ${esc(objectMeasures(obj))}</div>
      <div class="row"><a href="#/match?object=${obj.id}">Find compatible textiles</a>
      ${canEdit() ? `<a href="#/objects/${obj.id}/edit">Change length and height</a>` : ""}</div>
    </li>`;
}

function sortObjects(list) {
  return list.slice().sort((a, b) => comparePlaceName(a.name, b.name) || comparePlaceName(a.kind, b.kind));
}

function roomBlock(name, objects) {
  const items = objects.length
    ? sortObjects(objects).map(objectLine).join("")
    : `<li class="muted small">No objects in this room.</li>`;
  return `<li>
      <h3>${esc(name || "No room yet")}</h3>
      <ul class="object-list">${items}</ul>
    </li>`;
}

function homeArt(seed) {
  const text = String(seed || "home");
  let n = 7;
  for (const ch of text) n = (n * 33 + ch.charCodeAt(0)) >>> 0;
  const walls = ["#f6f0e6", "#f4e4d4", "#e6efe4", "#eee6f3", "#e5eef3"][n % 5];
  const roof = ["#6d4c3d", "#5d6a46", "#3e586c", "#7b5342", "#684c60"][n % 5];
  const door = ["#2c241f", "#4a382e", "#2f4236", "#2e3c4c"][(n >>> 3) % 4];
  const leaf = ["#8c9a78", "#c4a574", "#7f9a8a", "#b7a0c0", "#8aa0b5"][(n >>> 5) % 5];
  const tree = 24 + (n % 30);
  return `<svg class="home-art" viewBox="0 0 320 188" aria-hidden="true">
      <rect width="320" height="188" fill="#f3eee6"/>
      <rect y="132" width="320" height="56" fill="#e4d5c3"/>
      <circle cx="${250 - (n % 30)}" cy="40" r="16" fill="#f6e7c1"/>
      <rect x="${tree}" y="104" width="8" height="32" rx="2" fill="#6d4c3d"/>
      <circle cx="${tree + 4}" cy="96" r="16" fill="${leaf}"/>
      <polygon points="78,96 160,40 242,96" fill="${roof}"/>
      <rect x="94" y="96" width="132" height="68" fill="${walls}"/>
      <rect x="148" y="120" width="26" height="44" rx="2" fill="${door}"/>
      <circle cx="168" cy="143" r="2" fill="#f6e7c1"/>
      <rect x="110" y="110" width="24" height="20" fill="#f7f4ee" stroke="${roof}" stroke-width="3"/>
      <rect x="186" y="110" width="24" height="20" fill="#f7f4ee" stroke="${roof}" stroke-width="3"/>
      <rect x="150" y="28" width="12" height="26" fill="${roof}"/>
    </svg>`;
}

function homePicture(board) {
  if (board.hasPhoto) return `<img class="home-photo" src="${homePhotoUrl(board.id)}" alt="">`;
  return homeArt(board.id + board.name);
}

function homeTile(board) {
  return `<li><a class="home-tile" href="#/objects/home/${encodeURIComponent(board.id)}">
      ${homePicture(board)}
      <span class="home-tile-name">${esc(board.name)}</span>
    </a></li>`;
}

async function loadHomeBoards() {
  const [objects, tree] = await Promise.all([api("/api/objects"), api("/api/locations/tree")]);
  const byHome = new Map();
  const loose = [];
  for (const obj of objects) {
    if (obj.home_id == null) {
      loose.push(obj);
      continue;
    }
    const homeKey = String(obj.home_id);
    if (!byHome.has(homeKey)) byHome.set(homeKey, new Map());
    const rooms = byHome.get(homeKey);
    const roomKey = obj.room_id == null ? "" : String(obj.room_id);
    if (!rooms.has(roomKey)) rooms.set(roomKey, []);
    rooms.get(roomKey).push(obj);
  }
  const knownHomes = new Set();
  const homes = (tree.homes || []).slice().sort((a, b) => comparePlaceName(a.name, b.name));
  const boards = homes.map((home) => {
    const homeKey = String(home.id);
    knownHomes.add(homeKey);
    const roomMap = byHome.get(homeKey) || new Map();
    const knownRooms = new Set();
    const rooms = (home.rooms || []).slice().sort((a, b) => comparePlaceName(a.name, b.name));
    const roomHtml = rooms.map((room) => {
      knownRooms.add(String(room.id));
      return roomBlock(room.name, roomMap.get(String(room.id)) || []);
    });
    const extraRooms = [...roomMap.entries()]
      .filter(([roomId]) => roomId && !knownRooms.has(roomId))
      .map(([, list]) => ({ name: (list[0] && list[0].room_name) || "", objects: list }))
      .sort((a, b) => comparePlaceName(a.name, b.name));
    for (const room of extraRooms) roomHtml.push(roomBlock(room.name, room.objects));
    if (roomMap.has("")) roomHtml.push(roomBlock("", roomMap.get("")));
    return { id: homeKey, name: home.name, hasPhoto: Boolean(home.has_photo), html: roomHtml.length ? roomHtml.join("") : `<li class="muted">No rooms yet.</li>` };
  });
  for (const [homeKey, roomMap] of byHome) {
    if (knownHomes.has(homeKey)) continue;
    const named = [...roomMap.entries()].filter(([roomId]) => roomId);
    const first = named.flatMap(([, list]) => list)[0] || (roomMap.get("") || [])[0];
    const roomHtml = named
      .map(([, list]) => ({ name: (list[0] && list[0].room_name) || "", objects: list }))
      .sort((a, b) => comparePlaceName(a.name, b.name))
      .map((room) => roomBlock(room.name, room.objects));
    if (roomMap.has("")) roomHtml.push(roomBlock("", roomMap.get("")));
    boards.push({ id: homeKey, name: (first && first.home_name) || "No home yet", hasPhoto: false, html: roomHtml.join("") });
  }
  boards.sort((a, b) => comparePlaceName(a.name, b.name));
  if (loose.length) boards.push({ id: "none", name: "No home yet", hasPhoto: false, html: roomBlock("", loose) });
  return boards;
}

async function objectsView() {
  const boards = await loadHomeBoards();
  const add = canEdit() ? `<a class="btn" href="#/objects/new">Add object</a>` : "";
  return `<div class="top"><h1>Beds, tables and windows</h1>${add}</div>
    ${boards.length ? `<ul class="home-tiles">${boards.map(homeTile).join("")}</ul>` : "<p>No homes yet.</p>"}`;
}

async function objectsHomeView(id) {
  const boards = await loadHomeBoards();
  const board = boards.find((item) => item.id === String(id));
  const add = canEdit() ? `<a class="btn" href="#/objects/new">Add object</a>` : "";
  if (!board) {
    return `<div class="top"><h1>Home not found</h1><a class="btn secondary" href="#/objects">All homes</a></div>`;
  }
  const photoForm = canEdit() && board.id !== "none" ? `<form id="home-photo-form" class="panel home-photo-form">
      <div class="home-preview">${homePicture(board)}</div>
      <p class="muted">Replace the house picture with a photograph. JPEG, PNG or WebP, up to 8 MB.</p>
      <label>Photograph<input name="file" type="file" accept="image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp" required></label>
      <div class="row">
        <button class="btn" type="submit">Use this photograph</button>
        ${board.hasPhoto ? `<button class="btn secondary" type="button" id="home-photo-clear">Use the drawing</button>` : ""}
      </div>
      <p id="home-photo-error" class="banner error" hidden></p>
    </form>` : "";
  return `<div class="top"><div><a class="home-back" href="#/objects">All homes</a><h1>${esc(board.name)}</h1></div>${add}</div>
    ${photoForm}
    <section class="panel"><ul class="room-list">${board.html}</ul></section>`;
}

async function matchView() {
  const objects = await api("/api/objects");
  const selected = route().params.get("object") || (objects[0] && objects[0].id) || "";
  const objectOptions = groupObjects(objects).map((home) => home.rooms.map((room) => {
    const label = [home.name || "No home yet", room.name || "No room yet"].join(" · ");
    const options = room.objects.map((obj) => `<option value="${obj.id}" ${String(selected) === String(obj.id) ? "selected" : ""}>${esc(obj.kind)} — ${esc(obj.name)}</option>`).join("");
    return `<optgroup label="${esc(label)}">${options}</optgroup>`;
  }).join("")).join("");
  return `<div class="top"><h1>Matching</h1></div>
    <p class="muted">Technical fit is decided from measurements. Color is scored separately and never turns an incompatible size into a match.</p>
    <form id="match-form" class="filters">
      ${field("Object", `<select name="object_id">${objectOptions}</select>`)}
      ${field("Table overhang cm", `<input name="table_overhang_cm" type="number" min="0" step="0.1" placeholder="suggestion 25">`)}
      ${field("Curtain fullness", `<input name="curtain_fullness" type="number" min="0" step="0.1" placeholder="suggestion 2">`)}
      <button class="btn" type="submit">Check compatibility</button>
    </form>
    <div id="match-results"></div>`;
}

function renderMatch(result) {
  const combos = result.combinations || [];
  const missing = result.missing || [];
  const rejected = result.rejected || [];
  return `<p class="banner">${esc(result.preference_note || "")}</p>
    ${missing.map((row) => `<p class="banner">Missing ${esc(row.category)}: ${esc(row.reason)} Required: ${esc(row.required || "")}</p>`).join("")}
    ${combos.map((combo, index) => `<article class="panel combo">
      <h2>Combination ${index + 1}</h2>
      <p><span class="pill ${esc(combo.technical_status)}">Technical ${esc(combo.technical_status)}</span>
      ${combo.visual_score == null ? "" : `<span class="pill">Visual ${combo.visual_score}</span>`}</p>
      <p>${esc(combo.explanation || "")}</p>
      <p class="small">${esc(combo.visual_explanation || "")}</p>
      ${(combo.missing || []).map((row) => `<p class="small">Missing ${esc(row.category)} — ${esc(row.reason)} (${esc(row.required || "")})</p>`).join("")}
      <div class="items">${combo.items.map((item) => `<div><a href="#/items/${item.item_id}">${esc(item.name)}</a> · ${esc(item.role)} · ${esc(item.dimensions)} · ${esc((item.locations || []).join(", "))}
        <div class="small">${esc(item.technical.explanation || "")} ${(item.technical.warnings || []).map(esc).join(" ")}</div></div>`).join("")}</div>
      ${canEdit() ? `<button class="btn" data-save="${index}">Save this set</button>` : ""}
    </article>`).join("") || "<p>No technically compatible combination was found.</p>"}
    ${rejected.length ? `<h2>Not compatible</h2>` : ""}
    ${rejected.slice(0, 6).map((item) => `<p><a href="#/items/${item.item_id}">${esc(item.name)}</a> — ${esc(item.technical.explanation)}</p>`).join("")}`;
}

async function setsView() {
  const sets = await api("/api/sets");
  return `<div class="top"><h1>Saved sets</h1></div>
    ${sets.map((set) => `<article class="panel" style="margin-bottom:12px">
      <h2>${esc(set.name)} ${set.needs_attention ? `<span class="pill possible">Needs attention</span>` : ""}</h2>
      <p class="muted">${esc(set.object_name || "No linked object")}</p>
      ${set.items.map((item) => item.missing ? `<p>Missing item</p>` : `<p><a href="#/items/${item.id}">${esc(item.name)}</a> · ${(item.units[0] ? esc(placeLabel(item.units[0])) : "")}</p>`).join("")}
    </article>`).join("") || "<p>No saved sets yet. Save one from matching.</p>"}`;
}

async function familyView() {
  const family = await api("/api/family");
  const notes = await api("/api/notifications");
  return `<div class="top"><h1>${esc(family.name)}</h1><span class="pill">${esc(family.role)}</span></div>
    <section class="panel"><h2>Members</h2>
      <table>${family.members.map((member) => `<tr><td>${esc(member.full_name)}<br><span class="small muted">${esc(member.email)}</span></td><td>${esc(member.role)}</td>
        <td>${canAdmin() && member.id !== state.user.id ? `<button class="btn secondary" data-remove="${member.id}">Remove</button>` : ""}</td></tr>`).join("")}</table>
    </section>
    ${canAdmin() ? `<form id="invite-form" class="panel filters" style="margin-top:12px">
      <h2>Invite</h2>
      ${field("Email", `<input name="email" type="email" required>`)}
      ${field("Role", `<select name="role"><option>viewer</option><option>editor</option><option>admin</option></select>`)}
      <button class="btn" type="submit">Create invitation</button>
      <p id="invite-link" class="small"></p>
    </form>` : ""}
    <section class="panel" style="margin-top:12px"><h2>Pending invitations</h2>
      ${family.invitations.map((item) => `<p>${esc(item.email)} · ${esc(item.role)} · <code>#/accept/${esc(item.token)}</code></p>`).join("") || "<p>None.</p>"}
    </section>
    <section class="panel" style="margin-top:12px"><h2>Notifications</h2>
      ${notes.map((note) => `<p class="${note.read ? "muted" : ""}">${esc(note.message)}</p>`).join("") || "<p>None.</p>"}
    </section>`;
}

async function settingsView() {
  const family = await api("/api/family");
  const rules = await api("/api/rules");
  const prefs = family.preferences;
  return `<div class="top"><h1>Settings</h1></div>
    <form id="prefs" class="panel filters">
      <h2>Matching suggestions</h2>
      <p class="small muted">These defaults are labeled as suggestions in every result until you change them.</p>
      ${Object.entries(prefs).map(([key, value]) => field(key.replaceAll("_", " "), `<input name="${esc(key)}" type="number" min="0" step="0.1" value="${esc(value)}">`)).join("")}
      ${canAdmin() ? `<button class="btn" type="submit">Save preferences</button>` : `<p>Only an administrator can change these.</p>`}
    </form>
    <section class="panel" style="margin-top:12px"><h2>Compatibility relationships</h2>
      ${rules.map((rule) => `<p><label><input type="checkbox" data-rule="${rule.id}" ${rule.enabled ? "checked" : ""} ${canAdmin() ? "" : "disabled"}> ${esc(rule.relationship)}</label></p>`).join("")}
    </section>
    <section class="panel" style="margin-top:12px"><h2>Your data</h2>
      <p><a class="btn" href="#" id="export">Download inventory CSV</a></p>
      <label><input id="notify" type="checkbox" ${state.user.notify_changes ? "checked" : ""}> Tell me when someone changes the shared inventory</label>
    </section>`;
}

async function renderAccept(token) {
  const box = document.getElementById("invite-box");
  try {
    const preview = await fetch("/api/invitations/" + token).then((res) => res.json());
    if (!state.token) {
      box.innerHTML = `<p>${esc(preview.family_name)} invited ${esc(preview.email)} as ${esc(preview.role)}.</p><p><a href="#/login">Sign in</a> with that email, then open this invitation again.</p>`;
      return;
    }
    box.innerHTML = `<p>Join ${esc(preview.family_name)} as ${esc(preview.role)}?</p><button class="btn" id="join">Accept</button>`;
    document.getElementById("join").onclick = async () => {
      const result = await api("/api/family/invitations/accept", { method: "POST", body: { token } });
      state.memberships = result.memberships;
      go("#/dashboard");
    };
  } catch (error) {
    box.textContent = "This invitation is no longer available.";
  }
}

function bindPage(parts) {
  const filters = document.getElementById("filters");
  if (filters && parts[0] !== "item-form") {
    filters.onsubmit = (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(filters).entries());
      const params = new URLSearchParams();
      Object.entries(data).forEach(([key, value]) => { if (value) params.set(key, value); });
      go("#/inventory?" + params.toString());
    };
  }
  const category = document.getElementById("category");
  if (category) {
    renderExtraFields();
    category.onchange = renderExtraFields;
  }
  const ai = document.getElementById("ai-btn");
  if (ai) ai.onclick = suggestAi;
  const itemForm = document.getElementById("item-form");
  if (itemForm) itemForm.onsubmit = (event) => saveItem(event, false);
  const homePhoto = document.getElementById("home-photo-form");
  if (homePhoto && parts[0] === "objects" && parts[1] === "home" && parts[2]) {
    const showPhotoError = (error) => {
      const box = document.getElementById("home-photo-error");
      if (!box) return;
      box.hidden = false;
      box.textContent = messageOf(error);
    };
    homePhoto.onsubmit = async (event) => {
      event.preventDefault();
      const file = homePhoto.elements.file.files[0];
      if (!file) return;
      const body = new FormData();
      body.append("file", file);
      try {
        await api(`/api/homes/${parts[2]}/photo`, { method: "POST", body });
        await render();
      } catch (error) {
        showPhotoError(error);
      }
    };
    const clearPhoto = document.getElementById("home-photo-clear");
    if (clearPhoto) {
      clearPhoto.onclick = async () => {
        try {
          await api(`/api/homes/${parts[2]}/photo`, { method: "DELETE" });
          await render();
        } catch (error) {
          showPhotoError(error);
        }
      };
    }
  }
  const placeForm = document.getElementById("place-form");
  if (placeForm) {
    placeForm.onsubmit = savePlace;
    syncPlaceForm();
    placeForm.elements.kind.onchange = syncPlaceForm;
    placeForm.elements.home_id.onchange = syncPlaceForm;
    placeForm.elements.room_id.onchange = syncPlaceForm;
  }
  document.querySelectorAll("[data-edit-home]").forEach((button) => {
    button.onclick = () => {
      const editor = document.querySelector(`[data-home-editor="${button.dataset.editHome}"]`);
      if (editor) editor.hidden = !editor.hidden;
    };
  });
  document.querySelectorAll("[data-cancel-home]").forEach((button) => {
    button.onclick = () => {
      const editor = document.querySelector(`[data-home-editor="${button.dataset.cancelHome}"]`);
      if (editor) editor.hidden = true;
    };
  });
  document.querySelectorAll("[data-delete-room]").forEach((button) => {
    button.onclick = async () => {
      if (!confirm(`Delete ${button.dataset.roomName}?`)) return;
      try {
        await api("/api/rooms/" + button.dataset.deleteRoom, { method: "DELETE" });
        render();
      } catch (err) {
        showEditorError(button.dataset.homeId, err);
      }
    };
  });
  document.querySelectorAll("[data-delete-storage]").forEach((button) => {
    button.onclick = async () => {
      if (!confirm(`Delete ${button.dataset.storageName}?`)) return;
      try {
        await api("/api/storage/" + button.dataset.deleteStorage, { method: "DELETE" });
        render();
      } catch (err) {
        showEditorError(button.dataset.homeId, err);
      }
    };
  });
  document.querySelectorAll("[data-home-form]").forEach((form) => {
    form.onsubmit = async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      try {
        await api("/api/homes/" + form.dataset.homeForm, { method: "PATCH", body: { name: data.name } });
        render();
      } catch (err) {
        showHomesError(err);
      }
    };
  });
  document.querySelectorAll("[data-delete-home]").forEach((button) => {
    button.onclick = async () => {
      if (!confirm(`Delete ${button.dataset.homeName}? Its rooms disappear from the list.`)) return;
      try {
        await api("/api/homes/" + button.dataset.deleteHome, { method: "DELETE" });
        render();
      } catch (err) {
        showHomesError(err);
      }
    };
  });
  const objectForm = document.getElementById("object-form");
  if (objectForm) {
    bindMeasureFields(objectForm);
    syncObjectPlace();
    syncObjectKind();
    if (objectForm.elements.home_id) objectForm.elements.home_id.onchange = syncObjectPlace;
    if (objectForm.elements.kind) objectForm.elements.kind.onchange = syncObjectKind;
    objectForm.onsubmit = saveObject;
  }
  const matchForm = document.getElementById("match-form");
  if (matchForm) matchForm.onsubmit = runMatch;
  const inviteForm = document.getElementById("invite-form");
  if (inviteForm) inviteForm.onsubmit = sendInvite;
  document.querySelectorAll("[data-remove]").forEach((button) => {
    button.onclick = async () => {
      await api("/api/family/members/" + button.dataset.remove, { method: "DELETE" });
      render();
    };
  });
  const prefs = document.getElementById("prefs");
  if (prefs) prefs.onsubmit = savePrefs;
  document.querySelectorAll("[data-rule]").forEach((box) => {
    box.onchange = async () => {
      await api("/api/rules/" + box.dataset.rule, { method: "PATCH", body: { enabled: box.checked } });
    };
  });
  const notify = document.getElementById("notify");
  if (notify) notify.onchange = async () => {
    state.user = await api("/api/auth/me", { method: "PATCH", body: { notify_changes: notify.checked } });
  };
  const exportLink = document.getElementById("export");
  if (exportLink) exportLink.onclick = async (event) => {
    event.preventDefault();
    const response = await fetch("/api/export/inventory.csv", { headers: { Authorization: `Bearer ${state.token}`, "X-Family-Id": state.familyId } });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "inventory.csv";
    link.click();
    URL.revokeObjectURL(url);
  };
  const qr = document.getElementById("qr");
  if (qr) {
    const id = route().parts[1];
    fetch(`/api/storage/${id}/qr.png`, { headers: { Authorization: `Bearer ${state.token}`, "X-Family-Id": state.familyId } })
      .then((res) => res.blob())
      .then((blob) => { qr.src = URL.createObjectURL(blob); });
  }
}

async function suggestAi() {
  const input = document.getElementById("ai-file");
  const note = document.getElementById("ai-note");
  if (!input.files[0]) { note.textContent = "Choose a photograph first."; return; }
  const body = new FormData();
  body.append("file", input.files[0]);
  const result = await api("/api/ai/suggest", { method: "POST", body });
  window.__sources = result.field_sources || {};
  window.__aiOriginal = result.suggestions || {};
  const form = document.getElementById("item-form");
  Object.entries(result.suggestions || {}).forEach(([key, value]) => {
    const inputEl = form.elements[key];
    if (inputEl) inputEl.value = value;
  });
  note.textContent = result.disclaimer;
}

async function saveItem(event, acknowledge) {
  event.preventDefault();
  const form = event.target;
  const error = document.getElementById("form-error");
  const payload = collectItem(form, acknowledge);
  const existing = window.__formCache.existing;
  try {
    const saved = existing
      ? await api("/api/items/" + existing.id, { method: "PATCH", body: payload })
      : await api("/api/items", { method: "POST", body: payload });
    if (existing) await saveUnitLocations(form, existing);
    const file = document.getElementById("ai-file");
    if (file && file.files[0]) {
      const body = new FormData();
      body.append("file", file.files[0]);
      await api(`/api/items/${saved.id}/photos`, { method: "POST", body });
    }
    go("#/items/" + saved.id);
  } catch (err) {
    if (err.status === 409 && err.detail && err.detail.duplicates) {
      const box = document.getElementById("dupes");
      box.innerHTML = `<div class="banner">${esc(err.detail.message)} ${err.detail.duplicates.map((item) => `<a href="#/items/${item.id}">${esc(item.name)}</a>`).join(", ")}
        <button class="btn" id="confirm-dupe" type="button">Create a new record anyway</button></div>`;
      document.getElementById("confirm-dupe").onclick = () => saveItem(event, true);
      return;
    }
    error.hidden = false;
    error.textContent = messageOf(err);
    if (err.status === 409 && err.detail && err.detail.item) go("#/items/" + err.detail.item.id + "/edit");
  }
}

async function saveUnitLocations(form, existing) {
  for (const unit of existing.units || []) {
    const input = form.elements[`unit_location_${unit.id}`];
    if (!input) continue;
    const next = input.value ? Number(input.value) : null;
    const previous = unit.location_id == null ? null : Number(unit.location_id);
    if (next === previous) continue;
    await api(`/api/units/${unit.id}`, {
      method: "PATCH",
      body: next == null ? { clear_location: true } : { location_id: next },
    });
  }
}

function placeChoices(tree, homeId, roomId) {
  const homes = tree.homes || [];
  const home = homes.find((item) => String(item.id) === String(homeId)) || homes[0];
  const rooms = home ? home.rooms || [] : [];
  const room = rooms.find((item) => String(item.id) === String(roomId)) || rooms[0];
  const parents = [];
  const walk = (nodes, prefix) => {
    for (const node of nodes || []) {
      const label = prefix ? `${prefix} / ${node.name}` : node.name;
      parents.push({ id: node.id, label });
      walk(node.children, label);
    }
  };
  if (room) walk(room.locations, "");
  return { homes, home, rooms, room, parents };
}

function fillSelect(select, options, selected, emptyLabel) {
  const html = (emptyLabel ? `<option value="">${esc(emptyLabel)}</option>` : "") + options.map((option) => `<option value="${option.id}">${esc(option.label)}</option>`).join("");
  select.innerHTML = html || `<option value="">${esc(emptyLabel || "Nothing to choose")}</option>`;
  if ([...select.options].some((option) => option.value === String(selected ?? ""))) select.value = String(selected ?? "");
}

function syncPlaceForm() {
  const form = document.getElementById("place-form");
  const tree = window.__placeTree || { homes: [] };
  if (!form) return;
  const kind = form.elements.kind.value;
  const choice = placeChoices(tree, form.elements.home_id.value, form.elements.room_id.value);
  fillSelect(form.elements.home_id, choice.homes.map((home) => ({ id: home.id, label: home.name })), choice.home && choice.home.id);
  fillSelect(form.elements.room_id, choice.rooms.map((room) => ({ id: room.id, label: room.name })), choice.room && choice.room.id);
  fillSelect(form.elements.parent_id, choice.parents, form.elements.parent_id.value, "Directly in the room");
  const show = (name, visible) => {
    const label = form.elements[name].closest("label");
    if (label) label.hidden = !visible;
  };
  show("home_id", kind !== "home");
  show("room_id", kind === "storage");
  show("parent_id", kind === "storage");
  show("location_type", kind === "storage");
  form.elements.name.placeholder = kind === "home" ? "Xavier, Saint-Malo" : kind === "room" ? "Bedroom" : "Box 4";
  const submit = document.getElementById("place-submit");
  if (submit) submit.textContent = kind === "home" ? "Add home" : kind === "room" ? "Add room" : "Add storage";
}

function showEditorError(homeId, err) {
  const error = document.querySelector(`[data-home-error="${homeId}"]`);
  if (!error) {
    showHomesError(err);
    return;
  }
  error.hidden = false;
  error.textContent = messageOf(err);
}

function showHomesError(err) {
  const error = document.getElementById("homes-error");
  if (!error) return;
  error.hidden = false;
  error.textContent = messageOf(err);
}

async function savePlace(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const error = document.getElementById("place-error");
  error.hidden = true;
  try {
    if (data.kind === "home") await api("/api/homes", { method: "POST", body: { name: data.name } });
    else if (data.kind === "room") {
      if (!data.home_id) throw new Error("Choose a home from the list first.");
      await api("/api/rooms", { method: "POST", body: { name: data.name, home_id: Number(data.home_id) } });
    } else {
      if (!data.room_id) throw new Error("Choose a room from the list first.");
      await api("/api/storage", { method: "POST", body: { name: data.name, room_id: Number(data.room_id), parent_id: data.parent_id ? Number(data.parent_id) : null, location_type: data.location_type || "shelf" } });
    }
    go("#/locations");
    render();
  } catch (err) {
    error.hidden = false;
    error.textContent = messageOf(err);
  }
}

async function saveObject(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const error = document.getElementById("object-error");
  error.hidden = true;
  const measureKeys = ["width", "length", "height", "diameter", "depth", "rail_width", "desired_length", "fullness", "overhang", "pillow_1_width", "pillow_1_length", "pillow_2_width", "pillow_2_length", "pillow_3_width", "pillow_3_length", "pillow_4_width", "pillow_4_length"];
  const number = (key) => {
    const raw = String(data[key] ?? "").trim().replace(",", ".");
    if (raw === "") return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : Number.NaN;
  };
  if (measureKeys.some((key) => data[key] !== "" && !(number(key) >= 0))) {
    error.hidden = false;
    error.textContent = "Type a measurement of zero or more. A negative number is not saved.";
    return;
  }
  const pillows = [1, 2, 3, 4].map((n) => {
    const width = number(`pillow_${n}_width`);
    const length = number(`pillow_${n}_length`);
    const pillow = {};
    if (width != null) pillow.width = width;
    if (length != null) pillow.length = length;
    return pillow;
  });
  const body = {
    kind: data.kind, name: data.name, shape: data.shape || "",
    home_id: data.home_id ? Number(data.home_id) : null,
    room_id: data.room_id ? Number(data.room_id) : null,
    width: number("width"), length: number("length"), height: number("height"),
    diameter: number("diameter"), depth: number("depth"), notes: data.notes || "",
    attributes: {
      rail_width: number("rail_width"), desired_length: number("desired_length"),
      fullness: number("fullness"), attachment: data.attachment || "", overhang: number("overhang"),
      pillows: data.kind === "bed" ? pillows : [],
    },
  };
  try {
    await api(data.object_id ? "/api/objects/" + data.object_id : "/api/objects", {
      method: data.object_id ? "PATCH" : "POST",
      body,
    });
    go("#/objects");
  } catch (err) {
    error.hidden = false;
    error.textContent = messageOf(err);
  }
}

let lastMatch = null;
async function runMatch(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const body = { object_id: Number(data.object_id) };
  if (data.table_overhang_cm) body.table_overhang_cm = Number(data.table_overhang_cm);
  if (data.curtain_fullness) body.curtain_fullness = Number(data.curtain_fullness);
  lastMatch = await api("/api/matching", { method: "POST", body });
  const box = document.getElementById("match-results");
  box.innerHTML = renderMatch(lastMatch);
  box.querySelectorAll("[data-save]").forEach((button) => {
    button.onclick = async () => {
      const combo = lastMatch.combinations[Number(button.dataset.save)];
      const name = prompt("Name this set", "Saved combination");
      if (!name) return;
      const roles = {};
      combo.items.forEach((item) => { roles[String(item.item_id)] = item.role; });
      await api("/api/sets", { method: "POST", body: {
        name, object_id: lastMatch.object.id, item_ids: [...new Set(combo.items.map((item) => item.item_id))], roles,
      }});
      go("#/sets");
    };
  });
}

async function sendInvite(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const result = await api("/api/family/invitations", { method: "POST", body: data });
  document.getElementById("invite-link").textContent = `Share this link: ${location.origin}/#/accept/${result.token}`;
}

async function savePrefs(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const body = {};
  Object.entries(data).forEach(([key, value]) => { body[key] = Number(value); });
  await api("/api/family/preferences", { method: "PATCH", body });
  go("#/settings");
}

window.addEventListener("hashchange", boot);
boot();
