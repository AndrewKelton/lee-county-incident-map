(() => {
  // ── Constants ──────────────────────────────────────────────────────────────

  const LEE_COUNTY_CENTER = [26.56, -81.87];
  const DEFAULT_ZOOM = 11;

  // Color palette keyed by incident nature (first word, lowercase)
  const NATURE_COLORS = {
    disturbance:  "#e74c3c",
    assault:      "#c0392b",
    theft:        "#e67e22",
    burglary:     "#d35400",
    traffic:      "#3498db",
    suspicious:   "#9b59b6",
    medical:      "#1abc9c",
    fire:         "#e74c3c",
    welfare:      "#27ae60",
    domestic:     "#c0392b",
    default:      "#7f8c8d",
  };

  // ── State ──────────────────────────────────────────────────────────────────

  let allIncidents = [];
  let markerLayer = null;
  let activeNatures = null; // null = all types shown

  // ── Map setup ──────────────────────────────────────────────────────────────

  const map = L.map("map").setView(LEE_COUNTY_CENTER, DEFAULT_ZOOM);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map);

  // ── Helpers ────────────────────────────────────────────────────────────────

  function markerColor(nature) {
    if (!nature) return NATURE_COLORS.default;
    const key = nature.trim().toLowerCase().split(/\s+/)[0];
    return NATURE_COLORS[key] || NATURE_COLORS.default;
  }

  function toTitleCase(str) {
    return str.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function circleMarker(incident) {
    return L.circleMarker([incident.lat, incident.lng], {
      radius: 7,
      fillColor: markerColor(incident.nature),
      color: "#fff",
      weight: 1,
      opacity: 0.9,
      fillOpacity: 0.85,
    }).bindPopup(buildPopup(incident));
  }

  function buildPopup(inc) {
    const date = inc.occuredDate
      ? inc.occuredDate.replace("T", " ").slice(0, 16)
      : "Unknown date";
    return `
      <div class="popup">
        <strong>${inc.nature || "Unknown"}</strong><br>
        <span class="popup-addr">${inc.address}, ${inc.city}</span><br>
        <span class="popup-date">${date}</span><br>
        <span class="popup-disp">${inc.disposition || ""}</span>
        <span class="popup-id">#${inc.incidentNumber || inc.id}</span>
      </div>`;
  }

  function filterByDays(incidents, days) {
    if (days === 0) return incidents;
    const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
    return incidents.filter((inc) => {
      if (!inc.occuredDate) return false;
      // Normalize to ISO 8601 for Safari: replace space, truncate to 3 decimal places
      const normalized = inc.occuredDate.replace(" ", "T").replace(/(\.\d{3})\d+/, "$1");
      return new Date(normalized).getTime() >= cutoff;
    });
  }

  function renderMarkers(incidents) {
    if (markerLayer) map.removeLayer(markerLayer);

    const mappable = incidents.filter(
      (inc) => inc.lat != null && inc.lng != null
    );

    markerLayer = L.layerGroup(mappable.map(circleMarker)).addTo(map);

    document.getElementById("count-badge").textContent =
      `${mappable.length.toLocaleString()} incident${mappable.length !== 1 ? "s" : ""}`;
  }

  function applyFilter() {
    const days = parseInt(
      document.getElementById("date-filter").value,
      10
    );
    let filtered = filterByDays(allIncidents, days);
    if (activeNatures !== null) {
      filtered = filtered.filter(
        (inc) => activeNatures.has(inc.nature || "Unknown")
      );
    }
    renderMarkers(filtered);
  }

  // ── Nature filter ──────────────────────────────────────────────────────────

  function buildNatureFilter(incidents) {
    const natures = [
      ...new Set(incidents.map((inc) => inc.nature || "Unknown")),
    ].sort();

    const panel = document.getElementById("nature-panel");
    panel.innerHTML = "";

    // "All types" master toggle
    const allLabel = document.createElement("label");
    allLabel.className = "nature-row nature-all";
    const allCb = document.createElement("input");
    allCb.type = "checkbox";
    allCb.id = "nature-cb-all";
    allCb.checked = true;
    allLabel.appendChild(allCb);
    allLabel.appendChild(document.createTextNode(" All types"));
    panel.appendChild(allLabel);

    const hr = document.createElement("hr");
    hr.className = "nature-divider";
    panel.appendChild(hr);

    // Per-nature rows
    for (const nature of natures) {
      const row = document.createElement("label");
      row.className = "nature-row";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = nature;
      cb.checked = true;
      cb.addEventListener("change", onNatureChange);
      const dot = document.createElement("span");
      dot.className = "nature-dot";
      dot.style.background = markerColor(nature);
      row.appendChild(cb);
      row.appendChild(dot);
      row.appendChild(document.createTextNode(" " + toTitleCase(nature)));
      panel.appendChild(row);
    }

    allCb.addEventListener("change", () => {
      panel
        .querySelectorAll("input[type=checkbox]:not(#nature-cb-all)")
        .forEach((cb) => { cb.checked = allCb.checked; });
      activeNatures = allCb.checked ? null : new Set();
      applyFilter();
      updateNatureBtn();
    });
  }

  function onNatureChange() {
    const checkboxes = [
      ...document.querySelectorAll("#nature-panel input[type=checkbox]:not(#nature-cb-all)"),
    ];
    const allCb = document.getElementById("nature-cb-all");
    const checked = checkboxes.filter((cb) => cb.checked).map((cb) => cb.value);

    if (checked.length === checkboxes.length) {
      activeNatures = null;
      allCb.checked = true;
      allCb.indeterminate = false;
    } else if (checked.length === 0) {
      activeNatures = new Set();
      allCb.checked = false;
      allCb.indeterminate = false;
    } else {
      activeNatures = new Set(checked);
      allCb.checked = false;
      allCb.indeterminate = true;
    }
    applyFilter();
    updateNatureBtn();
  }

  function updateNatureBtn() {
    const btn = document.getElementById("nature-filter-btn");
    if (activeNatures === null) {
      btn.textContent = "All types ▾";
      btn.classList.remove("nature-filtered");
    } else if (activeNatures.size === 0) {
      btn.textContent = "No types ▾";
      btn.classList.add("nature-filtered");
    } else {
      btn.textContent = `${activeNatures.size} type${activeNatures.size !== 1 ? "s" : ""} ▾`;
      btn.classList.add("nature-filtered");
    }
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  async function loadIncidents() {
    const overlay = document.getElementById("loading-overlay");
    const msg = document.getElementById("loading-msg");

    try {
      msg.textContent = "Fetching incidents…";
      const res = await fetch(`${API_BASE_URL}/api/incidents`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      allIncidents = await res.json();
      msg.textContent = `Geocoding complete. ${allIncidents.length} incidents loaded.`;

      buildNatureFilter(allIncidents);
      applyFilter();
      overlay.classList.add("hidden");
    } catch (err) {
      msg.textContent = `Error loading data: ${err.message}`;
      console.error(err);
    }
  }

  // ── Event listeners ────────────────────────────────────────────────────────

  document.getElementById("date-filter").addEventListener("change", applyFilter);

  document.getElementById("nature-filter-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    document.getElementById("nature-panel").classList.toggle("hidden");
  });

  document.getElementById("nature-panel").addEventListener("click", (e) => {
    e.stopPropagation();
  });

  document.addEventListener("click", () => {
    document.getElementById("nature-panel").classList.add("hidden");
  });

  // Report download

  document.getElementById("report-btn").addEventListener("click", async () => {
    const btn  = document.getElementById("report-btn");
    const days = parseInt(document.getElementById("date-filter").value, 10);
    const b    = map.getBounds();

    btn.textContent = "Generating…";
    btn.disabled    = true;

    try {
      const res = await fetch(`${API_BASE_URL}/api/report`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          days,
          bounds: {
            north: b.getNorth(),
            south: b.getSouth(),
            east:  b.getEast(),
            west:  b.getWest(),
          },
        }),
      });

      if (!res.ok) throw new Error(`Server error ${res.status}`);

      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `lee-county-report.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Report generation failed: ${err.message}`);
    } finally {
      btn.textContent = "⬇ Generate Report";
      btn.disabled    = false;
    }
  });

  // ── Boot ───────────────────────────────────────────────────────────────────

  loadIncidents();
})();
