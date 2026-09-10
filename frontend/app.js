const state = {
  bucket: "",
  selectedId: null,
  shipments: [],
};

const SAMPLES = [
  { file: "01_enroute_ontime.edi", label: "On-time en route" },
  { file: "03_carrier_delay.edi", label: "Carrier delay (A9)" },
  { file: "04_overdue.edi", label: "Missed promise" },
  { file: "02_delivered.edi", label: "Delivered" },
];

const $ = (id) => document.getElementById(id);

function apiKey() {
  const value = $("apiKey").value.trim();
  localStorage.setItem("shipvis.apiKey", value);
  return value;
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (options.auth) headers["X-API-Key"] = apiKey();
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

function fmtWhen(value) {
  if (!value) return "—";
  const d = new Date(value);
  return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function stamp(bucket, label) {
  return `<span class="stamp ${bucket}">${label}</span>`;
}

function renderKpis(stats) {
  $("kpis").innerHTML = `
    <div class="kpi"><b>${stats.total}</b><span>Bills on file</span></div>
    <div class="kpi transit"><b>${stats.in_transit}</b><span>In transit</span></div>
    <div class="kpi delayed"><b>${stats.delayed}</b><span>Delayed</span></div>
    <div class="kpi delivered"><b>${stats.delivered}</b><span>Delivered</span></div>
  `;
}

function renderList() {
  const q = $("search").value.toLowerCase();
  const rows = state.shipments.filter((s) => {
    if (state.bucket && s.bucket !== state.bucket) return false;
    if (!q) return true;
    return [s.pro_number, s.shipper_name, s.consignee_name, s.po_number].join(" ").toLowerCase().includes(q);
  });
  $("shipments").innerHTML = rows.map((s) => `
    <li>
      <button class="bill ${s.id === state.selectedId ? "selected" : ""}" data-id="${s.id}">
        <div class="pro">${s.scac} ${s.pro_number}</div>
        <small>${s.shipper_city || s.shipper_name} → ${s.consignee_city || s.consignee_name}</small>
        ${stamp(s.bucket, s.current_status_label)}
      </button>
    </li>
  `).join("") || `<li class="empty" style="padding:12px">No bills match.</li>`;
}

function renderDetail(s) {
  $("detail").innerHTML = `
    <div class="lane">
      <div><strong>${s.shipper_name || "Shipper"}</strong>${s.shipper_city}, ${s.shipper_state}</div>
      <div style="text-align:right"><strong>${s.consignee_name || "Consignee"}</strong>${s.consignee_city}, ${s.consignee_state}</div>
    </div>
    <h2>${s.scac} ${s.pro_number}</h2>
    ${stamp(s.bucket, s.current_status_label)}
    <dl class="meta">
      <div><dt>Shipment</dt><dd>${s.shipment_id || "—"}</dd></div>
      <div><dt>PO / BOL</dt><dd>${s.po_number || "—"} / ${s.bill_of_lading || "—"}</dd></div>
      <div><dt>Promised</dt><dd>${fmtWhen(s.promised_delivery)}</dd></div>
      <div><dt>Last ping</dt><dd>${s.current_city || "—"} ${s.current_state} · ${fmtWhen(s.last_event_at)}</dd></div>
    </dl>
    <h3>Event tape</h3>
    <ol class="tape">
      ${s.events.map((e) => `
        <li>
          <time>${fmtWhen(e.occurred_at)}</time>
          <div>
            <strong>${e.status_code} · ${e.status_label}</strong>
            <div>${[e.city, e.state, e.country].filter(Boolean).join(", ") || "Location not sent"}</div>
          </div>
        </li>
      `).join("")}
    </ol>
  `;
}

function renderAlerts(rows) {
  $("alerts").innerHTML = rows.map((n) => `
    <li>${fmtWhen(n.created_at)} · ${n.message}</li>
  `).join("") || `<li class="empty" style="padding:12px">No delay alerts yet.</li>`;
}

async function refresh() {
  const [stats, shipments, alerts] = await Promise.all([
    api("/api/stats"),
    api("/api/shipments"),
    api("/api/notifications"),
  ]);
  state.shipments = shipments;
  renderKpis(stats);
  renderList();
  renderAlerts(alerts);
  if (state.selectedId) {
    const detail = await api(`/api/shipments/${state.selectedId}`);
    renderDetail(detail);
  }
}

async function openShipment(id) {
  state.selectedId = id;
  renderList();
  renderDetail(await api(`/api/shipments/${id}`));
}

$("shipments").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-id]");
  if (btn) openShipment(Number(btn.dataset.id));
});

$("filters").addEventListener("click", (event) => {
  const btn = event.target.closest("button");
  if (!btn) return;
  state.bucket = btn.dataset.bucket;
  for (const child of $("filters").children) child.classList.toggle("active", child === btn);
  renderList();
});

$("search").addEventListener("input", renderList);
$("btnRefresh").addEventListener("click", () => refresh().catch((err) => alert(err.message)));
$("btnLesson").addEventListener("click", () => $("lessonDialog").showModal());
$("btnCloseLesson").addEventListener("click", () => $("lessonDialog").close());
$("btnIngest").addEventListener("click", () => {
  $("ingestError").hidden = true;
  $("ingestDialog").showModal();
});
$("btnCancelIngest").addEventListener("click", () => $("ingestDialog").close());

$("sampleButtons").innerHTML = SAMPLES.map((s) =>
  `<button type="button" data-sample="${s.file}">${s.label}</button>`
).join("");

$("sampleButtons").addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-sample]");
  if (!btn) return;
  const res = await fetch(`/samples/${btn.dataset.sample}`);
  if (res.ok) {
    $("ediInput").value = await res.text();
    return;
  }
  $("ingestError").hidden = false;
  $("ingestError").textContent = "Could not load sample from the server.";
});

$("btnSubmitIngest").addEventListener("click", async () => {
  $("ingestError").hidden = true;
  try {
    const result = await api("/api/ingest/edi214", {
      method: "POST",
      auth: true,
      body: JSON.stringify({ content: $("ediInput").value, filename: "dashboard.edi" }),
    });
    $("ingestDialog").close();
    state.selectedId = result.shipment.id;
    await refresh();
  } catch (err) {
    $("ingestError").hidden = false;
    $("ingestError").textContent = err.message;
  }
});

const savedKey = localStorage.getItem("shipvis.apiKey");
if (savedKey) $("apiKey").value = savedKey;

refresh().catch((err) => {
  $("detail").innerHTML = `<p class="empty">API is not reachable: ${err.message}</p>`;
});
