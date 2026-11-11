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
    ["#/search", "Search"],
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
    if (parts[0] === "dashboard") appEl.innerHTML = shell(await dashboardView());
    else if (parts[0] === "inventory" || parts[0] === "search") appEl.innerHTML = shell(await inventoryView());
    else if (parts[0] === "items" && parts[1] === "new") appEl.innerHTML = shell(await itemFormView(null));
    else if (parts[0] === "items" && parts[2] === "edit") appEl.innerHTML = shell(await itemFormView(parts[1]));
    else if (parts[0] === "items" && parts[1]) appEl.innerHTML = shell(await itemDetailView(parts[1]));
    else if (parts[0] === "locations" && parts[1]) appEl.innerHTML = shell(await locationDetailView(parts[1]));
    else if (parts[0] === "locations") appEl.innerHTML = shell(await locationsView());
    else if (parts[0] === "objects" && parts[1] === "new") appEl.innerHTML = shell(objectFormView());
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

function cards(items) {
  if (!items.length) return `<p class="muted">Nothing here yet.</p>`;
  return `<div class="grid">${items.map((item) => {
    const photo = item.photos && item.photos[0];
    const place = item.units && item.units[0] ? item.units[0].location_path : "No location";
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

async function inventoryView() {
  const categories = await api("/api/categories");
  const params = route().params;
  const query = new URLSearchParams();
  ["q", "category_id", "color", "material", "pattern", "status", "seasonality", "sort"].forEach((key) => {
    if (params.get(key)) query.set(key, params.get(key));
  });
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
      ${field("Category", `<select name="category_id"><option value="">Any</option>${categories.map((c) => `<option value="${c.id}" ${params.get("category_id") == c.id ? "selected" : ""}>${esc(c.group_name)} — ${esc(c.name)}</option>`).join("")}</select>`)}
      ${field("Color", `<input name="color" list="colors" value="${esc(params.get("color") || "")}">`)}
      ${field("Material", `<input name="material" list="materials" value="${esc(params.get("material") || "")}">`)}
      ${field("Pattern", `<input name="pattern" list="patterns" value="${esc(params.get("pattern") || "")}">`)}
      ${field("Status", `<select name="status"><option value="">Any</option>${state.meta.statuses.map((s) => `<option ${params.get("status") === s ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>`)}
      ${field("Sort", `<select name="sort">
        ${["name", "category", "width", "created", "location"].map((s) => `<option ${params.get("sort") === s ? "selected" : ""}>${s}</option>`).join("")}
      </select>`)}
      <button class="btn" type="submit">Apply</button>
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
          ${item.units.map((unit) => `<div class="row" style="margin-bottom:8px"><span class="pill ${esc(unit.status)}">${esc(unit.status.replaceAll("_", " "))}</span><span class="small">${esc(unit.location_path)}</span></div>`).join("") || "<p>No units.</p>"}
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
  const homes = tree.homes.map((home) => `<section class="panel" style="margin-bottom:12px"><h2>${esc(home.name)}</h2>
    ${home.rooms.map((room) => `<h3>${esc(room.name)}</h3>${renderTree(room.locations)}`).join("") || `<p class="muted">No rooms yet.</p>`}
  </section>`).join("");
  return `<div class="top"><h1>Homes and storage</h1></div>
    ${canEdit() ? `<form id="place-form" class="panel filters" style="margin-bottom:12px">
      ${field("Add", `<select name="kind"><option value="home">Home</option><option value="room">Room</option><option value="storage">Storage location</option></select>`)}
      ${field("Name", `<input name="name" required placeholder="Box 4">`)}
      ${field("Home id for a room", `<input name="home_id" placeholder="from the list below">`)}
      ${field("Room id for storage", `<input name="room_id">`)}
      ${field("Parent location id", `<input name="parent_id">`)}
      ${field("Type", `<input name="location_type" placeholder="shelf, drawer, box, cupboard">`)}
      <button class="btn" type="submit">Add</button>
    </form>` : ""}
    ${homes || "<p>No homes yet.</p>"}`;
}

function renderTree(nodes) {
  if (!nodes || !nodes.length) return "";
  return `<ul>${nodes.map((node) => `<li><a href="#/locations/${node.id}">${esc(node.name)}</a> <span class="muted small">${esc(node.location_type)} · #${node.id}</span>${renderTree(node.children)}</li>`).join("")}</ul>`;
}

async function locationDetailView(id) {
  const data = await api("/api/storage/" + id);
  const qr = `/api/storage/${id}/qr.png`;
  return `<div class="top"><h1>${esc(data.name)}</h1></div>
    <section class="panel"><p>${esc(data.path)}</p><p class="muted">${esc(data.type)}</p>
    <img id="qr" alt="QR code for this location" style="width:180px;height:180px;background:#fff">
    <h2>Items here</h2>
    ${data.items.map((item) => `<p><a href="#/items/${item.id}">${esc(item.name)}</a> · ${esc(item.category)} · ${item.quantity_here}</p>`).join("") || "<p>This location is empty.</p>"}
    </section>`;
}

function objectFormView() {
  return `<div class="top"><h1>Add a household object</h1></div>
    <form id="object-form" class="panel filters">
      ${field("Type", `<select name="kind"><option value="bed">Bed</option><option value="mattress">Mattress</option><option value="table">Table</option><option value="window">Window</option></select>`)}
      ${field("Name", `<input name="name" required>`)}
      ${field("Shape", `<input name="shape" placeholder="rectangular, round, oval">`)}
      ${field("Width cm", `<input name="width" type="number" step="0.1">`)}
      ${field("Length cm", `<input name="length" type="number" step="0.1">`)}
      ${field("Height cm", `<input name="height" type="number" step="0.1">`)}
      ${field("Diameter cm", `<input name="diameter" type="number" step="0.1">`)}
      ${field("Mattress depth cm", `<input name="depth" type="number" step="0.1">`)}
      ${field("Curtain rail width", `<input name="rail_width" type="number" step="0.1">`)}
      ${field("Desired curtain length", `<input name="desired_length" type="number" step="0.1">`)}
      ${field("Fullness ratio", `<input name="fullness" type="number" step="0.1" placeholder="2">`)}
      ${field("Attachment", `<input name="attachment" placeholder="eyelets">`)}
      ${field("Preferred table overhang cm", `<input name="overhang" type="number" step="0.1">`)}
      ${field("Notes", `<textarea name="notes"></textarea>`)}
      <button class="btn" type="submit">Save object</button>
    </form>`;
}

async function objectsView() {
  const objects = await api("/api/objects");
  return `<div class="top"><h1>Beds, tables and windows</h1>${canEdit() ? `<a class="btn" href="#/objects/new">Add object</a>` : ""}</div>
    <div class="grid">${objects.map((obj) => `<article class="card"><div class="body"><strong>${esc(obj.name)}</strong>
      <div class="small muted">${esc(obj.kind)} · ${esc(obj.home_name)} ${esc(obj.room_name)}</div>
      <div>${esc(obj.dimensions_label)}${obj.depth ? ` · depth ${esc(obj.depth)} cm` : ""}</div>
      <a href="#/match?object=${obj.id}">Find compatible textiles</a></div></article>`).join("") || "<p>No household objects yet.</p>"}</div>`;
}

async function matchView() {
  const objects = await api("/api/objects");
  const selected = route().params.get("object") || (objects[0] && objects[0].id) || "";
  return `<div class="top"><h1>Matching</h1></div>
    <p class="muted">Technical fit is decided from measurements. Color is scored separately and never turns an incompatible size into a match.</p>
    <form id="match-form" class="filters">
      ${field("Object", `<select name="object_id">${objects.map((obj) => `<option value="${obj.id}" ${String(selected) === String(obj.id) ? "selected" : ""}>${esc(obj.kind)} — ${esc(obj.name)}</option>`).join("")}</select>`)}
      ${field("Table overhang cm", `<input name="table_overhang_cm" type="number" step="0.1" placeholder="suggestion 25">`)}
      ${field("Curtain fullness", `<input name="curtain_fullness" type="number" step="0.1" placeholder="suggestion 2">`)}
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
      ${set.items.map((item) => item.missing ? `<p>Missing item</p>` : `<p><a href="#/items/${item.id}">${esc(item.name)}</a> · ${(item.units[0] ? esc(item.units[0].location_path) : "")}</p>`).join("")}
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
      ${Object.entries(prefs).map(([key, value]) => field(key.replaceAll("_", " "), `<input name="${esc(key)}" type="number" step="0.1" value="${esc(value)}">`)).join("")}
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
  const placeForm = document.getElementById("place-form");
  if (placeForm) placeForm.onsubmit = savePlace;
  const objectForm = document.getElementById("object-form");
  if (objectForm) objectForm.onsubmit = saveObject;
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

async function savePlace(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  if (data.kind === "home") await api("/api/homes", { method: "POST", body: { name: data.name } });
  else if (data.kind === "room") await api("/api/rooms", { method: "POST", body: { name: data.name, home_id: Number(data.home_id) } });
  else await api("/api/storage", { method: "POST", body: { name: data.name, room_id: Number(data.room_id), parent_id: data.parent_id ? Number(data.parent_id) : null, location_type: data.location_type || "storage" } });
  go("#/locations");
  render();
}

async function saveObject(event) {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  const number = (key) => data[key] === "" ? null : Number(data[key]);
  await api("/api/objects", { method: "POST", body: {
    kind: data.kind, name: data.name, shape: data.shape || "",
    width: number("width"), length: number("length"), height: number("height"),
    diameter: number("diameter"), depth: number("depth"), notes: data.notes || "",
    attributes: {
      rail_width: number("rail_width"), desired_length: number("desired_length"),
      fullness: number("fullness"), attachment: data.attachment || "", overhang: number("overhang"),
    },
  }});
  go("#/objects");
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
