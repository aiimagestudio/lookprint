(() => {
  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  const state = {
    tab: "overview",
    project: null,
    fingerprint: null,
    metricMeta: [],
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

  const FAM_CLS = {
    "调色": "fam-tone",
    "光影·题材": "fam-light",
    "技术": "fam-tech",
    "偏离贡献": "fam-combo",
  };

  function diagHTML(row) {
    const dg = row.diagnosis;
    if (!dg || !dg.families || !dg.families.length) return "";
    const fams = dg.families
      .map((f) => `<div class="fam ${FAM_CLS[f.family] || ""}"><span>${f.family}</span>${f.hits.join(" · ")}</div>`)
      .join("");
    const advice = dg.advice ? `<span class="adv">${dg.advice}</span>` : "";
    return `<div class="verdict k-${dg.kind || "in"}">${dg.verdict}</div>${advice}${fams}`;
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
        if (j.status === "error") toast(j.error || "任务失败");
        else toast("完成");
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
    $("#projectTag").textContent = `${data.project.name} · ${data.project.gold_path}`;
    $("#projName").value = data.project.name;
    $("#goldPath").value = data.project.gold_path;
    $("#percentile").value = data.project.threshold_percentile;
    if (!data.has_fingerprint) {
      $("#heroStats").innerHTML = `<div class="stat"><span>还没有指纹</span><b>可在「项目」里分析</b></div>`;
    }
    return data;
  }

  function cardHTML(row, mode) {
    const d = Number(row.mahalanobis || 0).toFixed(2);
    const path = row.path;
    const diag = diagHTML(row);
    const pass = row.pass === true || (mode === "review" && Number(row.mahalanobis) < state.threshold);
    const badge = mode === "scan"
      ? `<span class="badge ${row.pass ? "pass" : "fail"}">${row.pass ? "符合" : "复核"} ${d}</span>`
      : `<span class="badge">${d}</span>`;
    let actions = "";
    if (mode === "review") {
      const on = row.decision || "";
      actions = `<div class="actions">
        <button data-act="keep" class="${on === "keep" ? "on-keep" : ""}">保留</button>
        <button data-act="maybe" class="${on === "maybe" ? "on-maybe" : ""}">待定</button>
        <button data-act="drop" class="${on === "drop" ? "on-drop" : ""}">剔除</button>
      </div>`;
    } else if (mode === "scan") {
      actions = `<div class="actions">
        <button data-act="mark" class="${row.marked ? "on-keep" : ""}">${row.marked ? "已标记" : "标记候选"}</button>
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

  async function loadOverview() {
    const ov = await api("/api/overview");
    state.overview = ov;
    state.fingerprint = ov.fingerprint;
    const fp = ov.fingerprint;
    if (!fp) {
      $("#heroStats").innerHTML = `<div class="stat"><span>未分析</span><b>打开「项目」页开始</b></div>`;
      return;
    }
    const cards = [
      ["图片数", fp.n_images, "金标准"],
      ["距离中位", fp.maha_median?.toFixed(2), "越小越像集合"],
      ["90 分位", fp.maha_p90?.toFixed(2), "默认离群阈值"],
      ["GMM 簇", fp.n_gmm_components, "1 = 风格单簇"],
    ];
    (ov.cards || []).slice(0, 4).forEach((c) => {
      cards.push([c.label, Number(c.median).toFixed(3), `IQR ${Number(c.q1).toFixed(3)}–${Number(c.q3).toFixed(3)}`]);
    });
    $("#heroStats").innerHTML = cards
      .map(([k, v, s]) => `<div class="stat"><span>${k}</span><b>${v ?? "—"}</b><span>${s}</span></div>`)
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
            label: "局部对比 × 饱和",
            data: points.map((p) => ({ x: p.x, y: p.y, file: p.file })),
            backgroundColor: points.map((p) => {
              const t = Math.min(1, (p.d - 3) / 8);
              return `hsla(${40 - t * 40}, 80%, 60%, 0.85)`;
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
          x: { title: { display: true, text: "局部对比", color: "#a8a49c" }, ticks: { color: "#a8a49c" }, grid: { color: "#2a2a34" } },
          y: { title: { display: true, text: "饱和度", color: "#a8a49c" }, ticks: { color: "#a8a49c" }, grid: { color: "#2a2a34" } },
        },
      },
    });
  }

  async function loadReview(fetchData = true) {
    if (fetchData) {
      const ov = state.overview || (await api("/api/overview"));
      state.overview = ov;
      const fp = ov.fingerprint || state.fingerprint;
      state.fingerprint = fp;
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
    $("#reviewCount").textContent = `${items.length} / ${state.review.length} 张离群 · 剩余 ${nAll - nDrop}/${nAll}`;
    const el = $("#reviewGrid");
    if (!items.length) {
      el.innerHTML = `<div class="empty">这个阈值下没有图片</div>`;
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
      $("#scanGrid").innerHTML = `<div class="empty">指定一个文件夹并扫描</div>`;
      $("#scanSummary").textContent = "";
      return;
    }
    $("#scanSummary").textContent = `${data.n_pass || 0} 符合 / ${data.n} 张 · 阈值 ${Number(data.threshold).toFixed(2)}`;
    const f = state.scanFilter;
    const items = data.items.filter((r) => {
      if (f === "pass") return r.pass;
      if (f === "review") return !r.pass;
      if (f === "marked") return r.marked;
      return true;
    });
    const el = $("#scanGrid");
    if (!items.length) {
      el.innerHTML = `<div class="empty">没有匹配的图片</div>`;
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
        <button data-act="keep" class="${on === "keep" ? "on-keep" : ""}">1 保留</button>
        <button data-act="maybe" class="${on === "maybe" ? "on-maybe" : ""}">2 待定</button>
        <button data-act="drop" class="${on === "drop" ? "on-drop" : ""}">3 剔除</button>`;
    } else if (mode === "scan") {
      actions.innerHTML = `<button data-act="mark" class="${row.marked ? "on-keep" : ""}">${row.marked ? "取消标记" : "标记候选"}</button>`;
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
    $("#fmTitle").textContent = target === "export" ? "导出到文件夹" : "选择文件夹";
    $("#fmPick").textContent = target === "export" ? "导出到此文件夹" : "使用此文件夹";
    let start = "";
    if (target === "gold") start = $("#goldPath").value || state.project?.gold_path || "";
    else if (target === "scan") start = $("#scanFolder").value;
    else if (target === "export") start = state.lastExportDir || parentDir(state.project?.gold_path || "");
    await renderBrowse(start || "");
  }

  async function doExport(kind, dest) {
    const r = await api("/api/export", { method: "POST", body: { dest, kind } });
    state.lastExportDir = dest;
    toast(`已复制 ${r.n} 张到 ${r.dest}（原图未删）`);
    return r;
  }

  async function renderBrowse(path) {
    const data = await api(`/api/browse?path=${encodeURIComponent(path || "")}`);
    $("#fmPath").textContent = data.path || "选择磁盘";
    $("#fmPath").dataset.path = data.path || "";
    $("#fmInfo").textContent = data.path ? `${data.n_images} 张图` : "";
    const rows = [];
    if (data.parent || data.path) {
      rows.push(`<button data-path="${encodeURIComponent(data.parent || "")}">.. 上级</button>`);
    }
    for (const d of data.dirs) {
      rows.push(`<button data-path="${encodeURIComponent(d.path)}">📁 ${d.name}</button>`);
    }
    $("#fmList").innerHTML = rows.join("") || "<div class='empty'>空</div>";
    $$("#fmList button").forEach((b) =>
      b.addEventListener("click", () => renderBrowse(decodeURIComponent(b.dataset.path)))
    );
  }



  function bind() {
    $$(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
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
        toast("请先进入一个文件夹");
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
        $("#settingsStatus").textContent = "已保存";
        toast("项目已保存");
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
      if (!items.length) return toast("没有符合项");
      await api("/api/candidates/mark", { method: "PUT", body: { paths: items.map((r) => r.path), marked: true } });
      items.forEach((r) => (r.marked = true));
      renderScan();
      toast(`已标记 ${items.length} 张`);
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
    bind();
    $("#folderModal").hidden = true;
    $("#lightbox").hidden = true;
    setTab("overview");
    await loadProject();
    await loadOverview();
  }

  boot().catch((e) => toast(e.message));
})();
