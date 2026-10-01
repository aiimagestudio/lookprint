(() => {
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
  const t = window.t;

  const state = {
    tab: "overview",
    lang: "zh",
    project: null,
    fingerprint: null,
    metricMeta: [],
    metricLabels: {},
    overview: null,
    review: [],
    reviewFilter: "",
    threshold: 7.57,
    scan: null,
    scanFilter: "pass",
    lb: { list: [], index: 0, mode: "review" },
    browseTarget: "scan",
    exportKind: "",
    lastExportDir: "",
    jobTimer: null,
    chart: null,
  };

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (el.hidden = true), 2800);
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail || JSON.stringify(j);
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  function rawUrl(path) {
    return `/api/raw?path=${encodeURIComponent(path)}`;
  }

  // ---- i18n helpers ----

  function langKey() {
    return state.lang;
  }

  function mLabel(key) {
    const m = state.metricLabels[key];
    if (!m) return key;
    return state.lang === "en" ? m.en || m.zh : m.zh || m.en;
  }

  function applyStatic() {
    document.documentElement.lang = state.lang === "en" ? "en" : "zh-CN";
    $$("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
    $$("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
    // 语言按钮显示当前语言（原生名），下拉里列出全部可选语言
    const cur = (window.LOOKPRINT_LANGUAGES || []).find((l) => l.code === state.lang);
    $("#langBtn").textContent = cur ? cur.name : state.lang;
    $("#langMenu").innerHTML = (window.LOOKPRINT_LANGUAGES || [])
      .map((l) => `<button data-lang="${l.code}" class="${l.code === state.lang ? "on" : ""}">${l.name}</button>`)
      .join("");
    $$("#langMenu button").forEach((b) =>
      b.addEventListener("click", () => {
        $("#langMenu").hidden = true;
        setLang(b.dataset.lang);
      })
    );
  }

  function setLang(lang) {
    state.lang = lang;
    localStorage.setItem("lookprint.lang", lang);
    window.LOOKPRINT_LANG = lang;
    applyStatic();
    if (state.tab === "overview") loadOverview();
    else if (state.tab === "review") loadReview(true);
    else if (state.tab === "scan") renderScan();
  }

  // ---- diagnosis rendering ----

  const FAM_CLS = {
    tone: "fam-tone",
    light: "fam-light",
    tech: "fam-tech",
    combo: "fam-combo",
  };

  function diagHTML(row) {
    const dg = row.diagnosis;
    if (!dg || !dg.families || !dg.families.length) return "";
    const kind = dg.kind || "in";
    const near = dg.near && (kind === "tone" || kind === "multi" || kind === "tech");
    const vKey = near ? `v_${kind}_near` : `v_${kind}`;
    const aKey = near ? `a_${kind}_near` : `a_${kind}`;
    const fams = dg.families
      .map((f) => {
        const hits = f.hits
          .map((h) => {
            const label = mLabel(h.key);
            if (h.z != null) return `${label} ${h.z >= 0 ? "+" : ""}${h.z}σ`;
            return `${label}${state.lang === "en" ? " " : ""}${t(h.dir === "low" ? "dir_low" : "dir_high")}`;
          })
          .join(" · ");
        return `<div class="fam ${FAM_CLS[f.key] || ""}"><span>${t(`f_${f.key}`)}</span>${hits}</div>`;
      })
      .join("");
    const advice = t(aKey) ? `<span class="adv">${t(aKey)}</span>` : "";
    return `<div class="verdict k-${kind}">${t(vKey)}</div>${advice}${fams}`;
  }

  function setTab(name) {
    state.tab = name;
    $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
    if (name === "review") loadReview();
    if (name === "scan") loadScan();
    if (name === "overview") loadOverview();
  }

  function startJobPoll(job) {
    $("#jobBar").hidden = false;
    const tick = async () => {
      try {
        const j = await api(`/api/jobs/${job.id}`);
        $("#jobText").textContent = j.message || j.status;
        const pct = j.total ? (100 * j.current) / j.total : j.status === "done" ? 100 : 8;
        $("#jobFill").style.width = `${pct}%`;
        if (j.status === "running") {
          state.jobTimer = setTimeout(tick, 400);
          return;
        }
        if (j.status === "error") toast(j.error || "error");
        else toast(t("done"));
        setTimeout(() => ($("#jobBar").hidden = true), 1200);
        loadProject();
        if (j.kind === "analyze") loadOverview();
        if (j.kind === "scan") loadScan();
      } catch (e) {
        toast(e.message);
      }
    };
    tick();
  }

  async function loadProject() {
    const data = await api("/api/project");
    state.project = data.project;
    state.metricMeta = data.metric_meta;
    state.metricLabels = data.metric_labels || {};
    $("#projectTag").textContent = `${data.project.name} · ${data.project.gold_path || "—"}`;
    $("#projName").value = data.project.name;
    $("#goldPath").value = data.project.gold_path;
    $("#percentile").value = data.project.threshold_percentile;
    if (!data.has_fingerprint) {
      $("#heroStats").innerHTML = "";
    }
    return data;
  }

  function cardHTML(row, mode) {
    const d = Number(row.mahalanobis || 0).toFixed(2);
    const path = row.path;
    const diag = diagHTML(row);
    const pass = row.pass === true || (mode === "review" && Number(row.mahalanobis) < state.threshold);
    const badge = mode === "scan"
      ? `<span class="badge ${row.pass ? "pass" : "fail"}">${row.pass ? t("b_pass") : t("b_review")} ${d}</span>`
      : `<span class="badge">${d}</span>`;
    let actions = "";
    if (mode === "review") {
      const on = row.decision || "";
      actions = `<div class="actions">
        <button data-act="keep" class="${on === "keep" ? "on-keep" : ""}">${t("keep")}</button>
        <button data-act="maybe" class="${on === "maybe" ? "on-maybe" : ""}">${t("maybe")}</button>
        <button data-act="drop" class="${on === "drop" ? "on-drop" : ""}">${t("drop")}</button>
      </div>`;
    } else if (mode === "scan") {
      actions = `<div class="actions">
        <button data-act="mark" class="${row.marked ? "on-keep" : ""}">${row.marked ? t("marked") : t("mark")}</button>
      </div>`;
    }
    return `<article class="card" data-path="${encodeURIComponent(path)}" data-file="${row.file}" data-mode="${mode}">
      <img src="${rawUrl(path)}" alt="${row.file}" loading="lazy" />
      <div class="meta">
        <div class="name" title="${row.file}">${row.file}</div>
        ${badge}
        <div class="flags">${diag}</div>
        ${actions}
      </div>
    </article>`;
  }

  function bindGrid(el, list, mode) {
    el.querySelectorAll(".card").forEach((card, i) => {
      card.querySelector("img").addEventListener("click", () => openLb(list, i, mode));
      card.querySelectorAll("[data-act]").forEach((btn) => {
        btn.addEventListener("click", (ev) => {
          ev.stopPropagation();
          onAction(mode, list[i], btn.dataset.act);
        });
      });
    });
  }

  async function onAction(mode, row, act) {
    try {
      if (mode === "review") {
        await api("/api/decisions", { method: "PUT", body: { file: row.file, decision: act } });
        row.decision = act;
        loadReview(false);
      } else if (act === "mark") {
        const marked = !row.marked;
        await api("/api/candidates/mark", { method: "PUT", body: { paths: [row.path], marked } });
        row.marked = marked;
        renderScan();
      }
    } catch (e) {
      toast(e.message);
    }
  }

  function emptyGuideHTML() {
    return `
      <p>${t("go_setup_desc")}</p>
      <button class="primary" data-act="go-settings">${t("go_setup")}</button>`;
  }

  async function loadOverview() {
    const ov = await api("/api/overview");
    state.overview = ov;
    state.fingerprint = ov.fingerprint;
    const fp = ov.fingerprint;
    const guide = $("#emptyGuide");
    if (!fp) {
      $("#heroStats").innerHTML = "";
      guide.innerHTML = emptyGuideHTML();
      guide.hidden = false;
      guide.querySelector("[data-act='go-settings']").addEventListener("click", () => setTab("settings"));
      return;
    }
    guide.hidden = true;
    guide.innerHTML = "";
    const cards = [
      ["n_images", fp.n_images, "gold_sub"],
      ["median_dist", fp.maha_median?.toFixed(2), "median_dist_sub"],
      ["p90", fp.maha_p90?.toFixed(2), "p90_sub"],
      ["clusters", fp.n_gmm_components, "clusters_sub"],
    ];
    (ov.cards || []).slice(0, 4).forEach((c) => {
      const label = state.lang === "en" ? c.label_en || c.label : c.label;
      cards.push([label, Number(c.median).toFixed(3), `IQR ${Number(c.q1).toFixed(3)}–${Number(c.q3).toFixed(3)}`]);
    });
    const FIXED_LABELS = new Set(["n_images", "median_dist", "p90", "clusters"]);
    const FIXED_SUBS = new Set(["gold_sub", "median_dist_sub", "p90_sub", "clusters_sub"]);
    $("#heroStats").innerHTML = cards
      .map(([k, v, s]) => `<div class="stat"><span>${FIXED_LABELS.has(k) ? t(k) : k}</span><b>${v ?? "—"}</b><span>${FIXED_SUBS.has(s) ? t(s) : s}</span></div>`)
      .join("");
    $("#typicalGrid").innerHTML = ov.typical.map((r) => cardHTML(r, "preview")).join("");
    $("#outlierPreview").innerHTML = ov.outliers.map((r) => cardHTML(r, "preview")).join("");
    bindGrid($("#typicalGrid"), ov.typical, "preview");
    bindGrid($("#outlierPreview"), ov.outliers, "preview");
    $("#plots").innerHTML = (ov.plots || [])
      .map((n) => `<img src="/api/plots/${n}?t=${Date.now()}" alt="${n}" />`)
      .join("");
    drawScatter(ov.scatter || []);
  }

  function drawScatter(points) {
    const canvas = $("#scatterChart");
    if (!window.Chart || !points.length) return;
    if (state.chart) state.chart.destroy();
    state.chart = new Chart(canvas, {
      type: "scatter",
      data: {
        datasets: [
          {
            label: t("chart_label"),
            data: points.map((p) => ({ x: p.x, y: p.y, file: p.file })),
            backgroundColor: points.map((p) => {
              const dd = Math.min(1, (p.d - 3) / 8);
              return `hsla(${40 - dd * 40}, 80%, 60%, 0.85)`;
            }),
          },
        ],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#d8d4cc" } },
          tooltip: { callbacks: { label: (c) => c.raw.file } },
        },
        scales: {
          x: { title: { display: true, text: t("axis_x"), color: "#a8a49c" }, ticks: { color: "#a8a49c" }, grid: { color: "#2a2a34" } },
          y: { title: { display: true, text: t("axis_y"), color: "#a8a49c" }, ticks: { color: "#a8a49c" }, grid: { color: "#2a2a34" } },
        },
      },
    });
  }

  async function loadReview(fetchData = true) {
    if (fetchData) {
      const ov = state.overview || (await api("/api/overview"));
      state.overview = ov;
      state.fingerprint = ov.fingerprint || state.fingerprint;
      const fp = state.fingerprint;
      const slider = $("#dSlider");
      const maxD = Math.max(8, ...((ov.scatter || []).map((p) => Number(p.d) || 0)));
      slider.min = "2";
      slider.max = String(Math.ceil(maxD * 10) / 10);
      if (!slider.dataset.ready) {
        slider.value = fp?.maha_p90 ?? 7.57;
        slider.dataset.ready = "1";
      }
      const cut = Number(slider.value);
      state.threshold = cut;
      $("#dValue").textContent = cut.toFixed(2);
      const data = await api(`/api/outliers?min_d=${cut}`);
      state.review = data.items;
    }
    const f = state.reviewFilter;
    const items = state.review.filter((r) => {
      if (f === "open") return !r.decision;
      if (f) return r.decision === f;
      return true;
    });
    const nAll = (state.overview && state.overview.n_metrics) || 0;
    const nDrop = ((state.overview && state.overview.decisions) || {}).drop || 0;
    $("#reviewCount").textContent = t("review_count", { a: items.length, b: state.review.length, c: nAll - nDrop, d: nAll });
    const el = $("#reviewGrid");
    if (!items.length) {
      el.innerHTML = `<div class="empty">${t("empty_cut")}</div>`;
      return;
    }
    el.innerHTML = items.map((r) => cardHTML(r, "review")).join("");
    bindGrid(el, items, "review");
  }

  async function loadScan() {
    state.scan = await api("/api/scan/last");
    if (state.scan?.folder) $("#scanFolder").value = state.scan.folder;
    renderScan();
  }

  function renderScan() {
    const data = state.scan;
    if (!data || !data.items) {
      $("#scanGrid").innerHTML = `<div class="empty">${t("empty_scan")}</div>`;
      $("#scanSummary").textContent = "";
      return;
    }
    $("#scanSummary").textContent = t("scan_summary", {
      p: data.n_pass || 0,
      n: data.n,
      t: Number(data.threshold).toFixed(2),
    });
    const f = state.scanFilter;
    const items = data.items.filter((r) => {
      if (f === "pass") return r.pass;
      if (f === "review") return !r.pass;
      if (f === "marked") return r.marked;
      return true;
    });
    const el = $("#scanGrid");
    if (!items.length) {
      el.innerHTML = `<div class="empty">${t("no_match")}</div>`;
      return;
    }
    el.innerHTML = items.map((r) => cardHTML(r, "scan")).join("");
    bindGrid(el, items, "scan");
  }

  function openLb(list, index, mode) {
    state.lb = { list, index, mode };
    const row = list[index];
    if (!row) return;
    $("#lightbox").hidden = false;
    $("#lbImg").src = rawUrl(row.path);
    $("#lbName").textContent = row.file;
    $("#lbDist").textContent = `  d=${Number(row.mahalanobis || 0).toFixed(2)}`;
    $("#lbFlags").innerHTML = diagHTML(row);
    const actions = $("#lbActions");
    if (mode === "review") {
      const on = row.decision || "";
      actions.innerHTML = `
        <button data-act="keep" class="${on === "keep" ? "on-keep" : ""}">${t("k_keep")}</button>
        <button data-act="maybe" class="${on === "maybe" ? "on-maybe" : ""}">${t("k_maybe")}</button>
        <button data-act="drop" class="${on === "drop" ? "on-drop" : ""}">${t("k_drop")}</button>`;
    } else if (mode === "scan") {
      actions.innerHTML = `<button data-act="mark" class="${row.marked ? "on-keep" : ""}">${row.marked ? t("unmark") : t("mark")}</button>`;
    } else actions.innerHTML = "";
    actions.querySelectorAll("[data-act]").forEach((b) =>
      b.addEventListener("click", () => onAction(mode, row, b.dataset.act).then(() => openLb(state.lb.list, state.lb.index, mode)))
    );
  }

  function lbNav(dir) {
    const n = state.lb.list.length;
    if (!n) return;
    state.lb.index = (state.lb.index + dir + n) % n;
    openLb(state.lb.list, state.lb.index, state.lb.mode);
  }

  function parentDir(p) {
    if (!p) return "";
    return p.replace(/[\\/]+$/, "").replace(/[\\/][^\\/]+$/, "");
  }

  async function pickFolder(target, opts = {}) {
    state.browseTarget = target;
    state.exportKind = opts.kind || "";
    $("#folderModal").hidden = false;
    $("#fmTitle").textContent = target === "export" ? t("export_to") : t("select_folder");
    $("#fmPick").textContent = target === "export" ? t("export_here") : t("use_this");
    let start = "";
    if (target === "gold") start = $("#goldPath").value || state.project?.gold_path || "";
    else if (target === "scan") start = $("#scanFolder").value;
    else if (target === "export") start = state.lastExportDir || parentDir(state.project?.gold_path || "");
    await renderBrowse(start || "");
  }

  async function doExport(kind, dest) {
    const r = await api("/api/export", { method: "POST", body: { dest, kind } });
    state.lastExportDir = dest;
    toast(t("copied", { n: r.n, d: r.dest }));
    return r;
  }

  async function renderBrowse(path) {
    const data = await api(`/api/browse?path=${encodeURIComponent(path || "")}`);
    $("#fmPath").textContent = data.path || t("pick_drive");
    $("#fmPath").dataset.path = data.path || "";
    $("#fmInfo").textContent = data.path ? t("n_images_fmt", { n: data.n_images }) : "";
    const rows = [];
    if (data.parent || data.path) {
      rows.push(`<button data-path="${encodeURIComponent(data.parent || "")}">${t("up_level")}</button>`);
    }
    for (const d of data.dirs) {
      rows.push(`<button data-path="${encodeURIComponent(d.path)}">📁 ${d.name}</button>`);
    }
    $("#fmList").innerHTML = rows.join("") || `<div class='empty'>${t("empty_list")}</div>`;
    $$("#fmList button").forEach((b) =>
      b.addEventListener("click", () => renderBrowse(decodeURIComponent(b.dataset.path)))
    );
  }

  function bind() {
    $$(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
    $("#langBtn").addEventListener("click", (e) => {
      e.stopPropagation();
      $("#langMenu").hidden = !$("#langMenu").hidden;
    });
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".lang-wrap")) $("#langMenu").hidden = true;
    });
    $("#dSlider").addEventListener("input", () => {
      $("#dValue").textContent = Number($("#dSlider").value).toFixed(2);
    });
    $("#dSlider").addEventListener("change", () => loadReview(true));
    $$("#decisionFilter button").forEach((b) =>
      b.addEventListener("click", () => {
        $$("#decisionFilter button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.reviewFilter = b.dataset.f;
        loadReview(false);
      })
    );
    $$("#scanFilter button").forEach((b) =>
      b.addEventListener("click", () => {
        $$("#scanFilter button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        state.scanFilter = b.dataset.f;
        renderScan();
      })
    );
    $("#browseBtn").addEventListener("click", () => pickFolder("scan"));
    $("#browseGold").addEventListener("click", () => pickFolder("gold"));
    $("#fmClose").addEventListener("click", () => ($("#folderModal").hidden = true));
    $("#fmPick").addEventListener("click", async () => {
      const p = $("#fmPath").dataset.path;
      if (!p) {
        toast(t("enter_folder"));
        return;
      }
      if (state.browseTarget === "gold") {
        $("#goldPath").value = p;
        $("#folderModal").hidden = true;
        return;
      }
      if (state.browseTarget === "scan") {
        $("#scanFolder").value = p;
        $("#folderModal").hidden = true;
        return;
      }
      if (state.browseTarget === "export") {
        $("#folderModal").hidden = true;
        try {
          await doExport(state.exportKind, p);
        } catch (e) {
          toast(e.message);
        }
      }
    });
    $("#scanBtn").addEventListener("click", async () => {
      try {
        const job = await api("/api/scan", {
          method: "POST",
          body: { folder: $("#scanFolder").value, recursive: $("#scanRecursive").checked },
        });
        startJobPoll(job);
      } catch (e) {
        toast(e.message);
      }
    });
    $("#saveProject").addEventListener("click", async () => {
      try {
        await api("/api/project", {
          method: "PUT",
          body: {
            name: $("#projName").value,
            gold_path: $("#goldPath").value,
            threshold_percentile: Number($("#percentile").value),
          },
        });
        $("#settingsStatus").textContent = t("saved");
        toast(t("toast_saved"));
        loadProject();
      } catch (e) {
        toast(e.message);
      }
    });
    $("#reanalyze").addEventListener("click", async () => {
      try {
        await api("/api/project", {
          method: "PUT",
          body: {
            name: $("#projName").value,
            gold_path: $("#goldPath").value,
            threshold_percentile: Number($("#percentile").value),
          },
        });
        const job = await api("/api/analyze", { method: "POST" });
        startJobPoll(job);
      } catch (e) {
        toast(e.message);
      }
    });
    $("#markPass").addEventListener("click", async () => {
      const items = (state.scan?.items || []).filter((r) => r.pass);
      if (!items.length) return toast(t("no_pass"));
      await api("/api/candidates/mark", { method: "PUT", body: { paths: items.map((r) => r.path), marked: true } });
      items.forEach((r) => (r.marked = true));
      renderScan();
      toast(t("marked_n", { n: items.length }));
    });
    $("#exportMarked").addEventListener("click", () => pickFolder("export", { kind: "candidates" }));
    $("#exportDropped").addEventListener("click", () => pickFolder("export", { kind: "dropped" }));
    $("#exportRemaining").addEventListener("click", () => pickFolder("export", { kind: "remaining" }));
    $("#lbClose").addEventListener("click", () => ($("#lightbox").hidden = true));
    $("#lbPrev").addEventListener("click", () => lbNav(-1));
    $("#lbNext").addEventListener("click", () => lbNav(1));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !$("#folderModal").hidden) {
        $("#folderModal").hidden = true;
        return;
      }
      if ($("#lightbox").hidden) return;
      if (e.key === "Escape") $("#lightbox").hidden = true;
      if (e.key === "ArrowLeft") lbNav(-1);
      if (e.key === "ArrowRight") lbNav(1);
      const row = state.lb.list[state.lb.index];
      if (!row) return;
      if (state.lb.mode === "review") {
        if (e.key === "1") onAction("review", row, "keep").then(() => lbNav(1));
        if (e.key === "2") onAction("review", row, "maybe").then(() => lbNav(1));
        if (e.key === "3") onAction("review", row, "drop").then(() => lbNav(1));
      }
    });
  }

  async function boot() {
    state.lang = localStorage.getItem("lookprint.lang") || ((navigator.language || "zh").toLowerCase().startsWith("zh") ? "zh" : "en");
    window.LOOKPRINT_LANG = state.lang;
    applyStatic();
    bind();
    $("#folderModal").hidden = true;
    $("#lightbox").hidden = true;
    setTab("overview");
    await loadProject();
    await loadOverview();
  }

  boot().catch((e) => toast(e.message));
})();
