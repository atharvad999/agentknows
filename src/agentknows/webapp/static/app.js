/* agentknows console */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const form = $("#query-form");
  const input = $("#query-input");
  const goBtn = $(".query__go");
  const sourcesSec = $("#sources");
  const sourceChips = $("#source-chips");
  const resultsSec = $("#results");
  const resultsMeta = $("#results-meta");
  const resultsBody = $("#results-body");
  const copyBtn = $("#copy-btn");
  const emptySec = $("#empty");
  const footStatus = $("#foot-status");
  const platformSelect = $("#platform-select");
  const readPlatformSelect = $("#read-platform-select");

  let verb = "research";
  let region = "";
  let limit = 8;
  let lastMarkdown = "";
  let activeStream = null;

  const PLACEHOLDERS = {
    research: "Ask the internet — e.g. UPI transaction limit changes",
    search: "Search — e.g. smallcap IT companies",
    read: "URL or ticker — e.g. https://forum.valuepickr.com/t/…  or RELIANCE",
    hot: "No query needed — pick a platform and run",
  };

  const HOT_PLATFORMS = ["news", "hackernews", "discourse"];

  /* ---------- tiny markdown renderer (headings, bold, links, lists, code) ---------- */

  const esc = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function inline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g,
      '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    return s;
  }

  function renderMarkdown(md) {
    const out = [];
    let inList = false;
    let inCode = false;
    const closeList = () => { if (inList) { out.push("</ul>"); inList = false; } };
    for (const raw of md.split("\n")) {
      if (raw.startsWith("```")) {
        closeList();
        out.push(inCode ? "</code></pre>" : "<pre><code>");
        inCode = !inCode;
        continue;
      }
      if (inCode) { out.push(esc(raw)); continue; }
      if (/^### /.test(raw)) { closeList(); out.push(`<h3>${inline(raw.slice(4))}</h3>`); }
      else if (/^## /.test(raw)) { closeList(); out.push(`<h2>${inline(raw.slice(3))}</h2>`); }
      else if (/^# /.test(raw)) { closeList(); out.push(`<h1>${inline(raw.slice(2))}</h1>`); }
      else if (/^\s*- /.test(raw)) {
        if (!inList) { out.push("<ul>"); inList = true; }
        out.push(`<li>${inline(raw.replace(/^\s*- /, ""))}</li>`);
      } else if (raw.trim() === "") { closeList(); }
      else { closeList(); out.push(`<p>${inline(raw)}</p>`); }
    }
    closeList();
    if (inCode) out.push("</code></pre>");
    return out.join("\n");
  }

  /* ---------- rendering ---------- */

  function showResults(meta) {
    emptySec.hidden = true;
    resultsSec.hidden = false;
    resultsMeta.textContent = meta;
  }

  function renderItems(result) {
    const ul = document.createElement("ul");
    ul.className = "items";
    for (const item of result.items || []) {
      const li = document.createElement("li");
      li.className = "item";
      const extras = Object.entries(item.extra || {})
        .filter(([, v]) => v !== null && v !== "")
        .map(([k, v]) => `<span>${esc(String(k))}: ${esc(String(v))}</span>`)
        .join("");
      li.innerHTML = `
        <h3 class="item__title">${item.url
          ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title || item.url)}</a>`
          : esc(item.title || "")}</h3>
        ${item.url ? `<p class="item__url">${esc(item.url)}</p>` : ""}
        ${item.snippet ? `<p class="item__snippet">${esc(item.snippet)}</p>` : ""}
        ${extras ? `<div class="item__extra">${extras}</div>` : ""}`;
      ul.appendChild(li);
    }
    if (!(result.items || []).length) {
      const li = document.createElement("li");
      li.className = "item";
      li.innerHTML = '<p class="item__snippet">(no results)</p>';
      ul.appendChild(li);
    }
    return ul;
  }

  function renderDoc(markdown) {
    const div = document.createElement("div");
    div.className = "doc";
    div.innerHTML = renderMarkdown(markdown);
    return div;
  }

  function renderError(payload) {
    const div = document.createElement("div");
    div.className = "error-card";
    div.innerHTML = `
      <p class="error-card__label">error${payload.platform ? " · " + esc(payload.platform) : ""}</p>
      <p>${esc(payload.error || "unknown error")}</p>
      ${payload.fix ? `<pre>${esc(payload.fix)}</pre>` : ""}`;
    return div;
  }

  function renderResult(payload, meta) {
    resultsBody.replaceChildren();
    copyBtn.hidden = true;
    if (!payload.ok) {
      showResults(meta || "failed");
      resultsBody.appendChild(renderError(payload));
      return;
    }
    showResults(meta || `${payload.platform} via ${payload.backend}`);
    if (payload.kind === "items") {
      resultsBody.appendChild(renderItems(payload));
    } else {
      lastMarkdown = payload.content || "";
      copyBtn.hidden = false;
      resultsBody.appendChild(renderDoc(lastMarkdown));
    }
  }

  /* ---------- verb / controls state ---------- */

  function setVerb(v) {
    verb = v;
    document.querySelectorAll(".verb").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.verb === v));
    document.querySelectorAll(".control").forEach((c) => {
      c.hidden = !c.dataset.for.split(" ").includes(v);
    });
    input.placeholder = PLACEHOLDERS[v];
    input.disabled = v === "hot";
    if (v === "hot") fillPlatforms(HOT_PLATFORMS);
    else if (v === "search") fillPlatforms(searchPlatforms);
    input.focus();
  }

  let searchPlatforms = ["web"];

  function fillPlatforms(list) {
    platformSelect.replaceChildren();
    for (const p of list) {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      platformSelect.appendChild(opt);
    }
  }

  document.querySelectorAll(".verb").forEach((b) =>
    b.addEventListener("click", () => setVerb(b.dataset.verb)));

  $("#region-seg").addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") return;
    region = e.target.dataset.value;
    e.currentTarget.querySelectorAll("button").forEach((b) =>
      b.classList.toggle("is-active", b === e.target));
  });

  $("#limit-seg").addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") return;
    limit = Number(e.target.dataset.value);
    e.currentTarget.querySelectorAll("button").forEach((b) =>
      b.classList.toggle("is-active", b === e.target));
  });

  /* ---------- run ---------- */

  function busy(on) {
    goBtn.disabled = on;
    footStatus.textContent = on ? "running…" : "idle";
  }

  async function runJSON(url, meta) {
    busy(true);
    sourcesSec.hidden = true;
    try {
      const resp = await fetch(url);
      renderResult(await resp.json(), meta);
    } catch (err) {
      renderResult({ ok: false, error: String(err) }, "failed");
    } finally {
      busy(false);
    }
  }

  function runResearch(q) {
    if (activeStream) activeStream.close();
    busy(true);
    resultsSec.hidden = true;
    sourcesSec.hidden = false;
    sourceChips.replaceChildren();
    const chipFor = {};

    const params = new URLSearchParams({ q, limit: String(limit) });
    if (region) params.set("region", region);
    const es = new EventSource(`/api/research/stream?${params}`);
    activeStream = es;

    es.addEventListener("plan", (e) => {
      for (const s of JSON.parse(e.data).sources) {
        const li = document.createElement("li");
        li.className = "is-pending";
        li.textContent = s;
        sourceChips.appendChild(li);
        chipFor[s] = li;
      }
    });

    es.addEventListener("source", (e) => {
      const d = JSON.parse(e.data);
      const chip = chipFor[d.source];
      if (!chip) return;
      chip.classList.remove("is-pending");
      chip.classList.add(d.ok ? "is-ok" : "is-fail");
      chip.innerHTML = d.ok
        ? `${esc(d.source)} <span class="chips__n">${d.count}</span>`
        : `${esc(d.source)} <span class="chips__n">×</span>`;
      if (!d.ok) chip.title = d.error || "";
    });

    es.addEventListener("bundle", (e) => {
      lastMarkdown = JSON.parse(e.data).markdown;
      showResults(`research · ${region || "both"} · ${limit}/source`);
      copyBtn.hidden = false;
      resultsBody.replaceChildren(renderDoc(lastMarkdown));
      es.close();
      activeStream = null;
      busy(false);
    });

    es.onerror = () => {
      es.close();
      activeStream = null;
      busy(false);
      if (resultsSec.hidden) {
        renderResult({ ok: false, error: "stream failed — is the server still running?" }, "failed");
      }
    };
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (verb !== "hot" && !q) { input.focus(); return; }

    if (verb === "research") return runResearch(q);

    if (verb === "search") {
      const p = platformSelect.value || "web";
      return runJSON(
        `/api/search?${new URLSearchParams({ q, platform: p, limit: String(limit) })}`,
        `search · ${p}`);
    }
    if (verb === "read") {
      const params = new URLSearchParams({ url: q });
      if (readPlatformSelect.value) params.set("platform", readPlatformSelect.value);
      return runJSON(`/api/read?${params}`, "read");
    }
    if (verb === "hot") {
      const p = platformSelect.value || "news";
      const params = new URLSearchParams({ platform: p, limit: String(limit) });
      if (p === "news" && region) params.set("region", region);
      return runJSON(`/api/hot?${params}`, `hot · ${p}`);
    }
  });

  copyBtn.addEventListener("click", async () => {
    await navigator.clipboard.writeText(lastMarkdown);
    copyBtn.textContent = "copied";
    setTimeout(() => (copyBtn.textContent = "copy markdown"), 1200);
  });

  /* ---------- doctor ---------- */

  const doctorDialog = $("#doctor-dialog");
  $("#doctor-btn").addEventListener("click", async () => {
    doctorDialog.showModal();
    const body = $("#doctor-body");
    body.innerHTML = '<p class="empty__dim">probing…</p>';
    try {
      const data = await (await fetch("/api/doctor")).json();
      body.replaceChildren();
      for (const ch of data.meta.channels) {
        const row = document.createElement("div");
        row.className = "doctor-row";
        row.title = ch.detail || "";
        row.innerHTML = `
          <span class="d-dot d-${esc(ch.status)}"></span>
          <span class="d-name">${esc(ch.platform)}</span>
          <span class="d-backend">${esc(ch.active_backend || ch.status)}</span>`;
        body.appendChild(row);
      }
    } catch (err) {
      body.innerHTML = `<p class="empty__dim">${esc(String(err))}</p>`;
    }
  });
  $("#doctor-close").addEventListener("click", () => doctorDialog.close());

  /* ---------- init ---------- */

  (async () => {
    try {
      const data = await (await fetch("/api/platforms")).json();
      if (data.hosted) {
        document.querySelector(".footer span").textContent =
          "agentknows · hosted demo — login-gated channels need the local install";
      }
      const plats = data.platforms || {};
      searchPlatforms = Object.keys(plats).filter((p) => plats[p].search);
      const readable = Object.keys(plats).filter((p) => plats[p].read);
      for (const p of readable) {
        const opt = document.createElement("option");
        opt.value = p;
        opt.textContent = p;
        readPlatformSelect.appendChild(opt);
      }
      if (verb === "search") fillPlatforms(searchPlatforms);
    } catch { /* server not ready — selects stay minimal */ }
  })();

  setVerb("research");
})();
