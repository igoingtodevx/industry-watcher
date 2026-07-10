// app.js — fetches latest.json and renders
(async function () {
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const slugify = (s) =>
    (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40) || "issue";

  function fmtDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleDateString("de-DE", { year: "numeric", month: "long", day: "numeric" });
  }
  function fmtShortDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  }
  function escape(s) {
    return (s || "").toString()
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function signalClass(s) {
    const v = (s || "").toLowerCase();
    if (v.includes("hoch") || v.includes("high")) return "signal";
    if (v.includes("mittel") || v.includes("mid")) return "signal signal-mid";
    if (v.includes("niedrig") || v.includes("low")) return "signal signal-soft";
    return "signal signal-mid";
  }
  function howClass(s) {
    return signalClass(s);
  }

  function renderBrief(data) {
    const b = data.brief || {};
    const meta = data;

    // Masthead
    const issueDate = new Date(meta.generated_at);
    const issueNum = `${issueDate.getFullYear()}-W${getISOWeek(issueDate)}`;
    $("#issue-num").textContent = `№ ${issueNum}`;

    // Hero
    $("#kicker-vertical").textContent = data.vertical || "—";
    $("#kicker-date").textContent = fmtDate(meta.generated_at);
    $("#headline").textContent = b.headline || "—";
    $("#subheadline").textContent = b.subheadline || "";

    // Masthead + Byline (editorial)
    const shortDate = new Date(meta.generated_at).toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" });
    $("#masthead-vertical").textContent = data.vertical || "—";
    $("#masthead-date").textContent = shortDate;
    $("#byline-date").textContent = shortDate;

    // Hero side: just show the issue date
    $("#hero-meta-date").textContent = shortDate;

    // Executive summary
    $("#exec-summary").innerHTML = b.executive_summary || "—";

    // Trends
    const tg = $("#trends-grid");
    tg.innerHTML = "";
    (b.trends || []).forEach((t) => {
      const div = document.createElement("div");
      div.className = "trend";
      div.innerHTML = `
        <span class="signal ${signalClass(t.signal)}">${escape(t.signal || "mittel")}</span>
        <h3>${escape(t.title)}</h3>
        <p>${escape(t.what || "")}</p>
        <p class="why"><strong>Warum relevant:</strong> ${escape(t.why || "")}</p>
      `;
      tg.appendChild(div);
    });
    if (!b.trends || b.trends.length === 0) {
      tg.innerHTML = "<p style='color: var(--ink-mute);'>Keine Trends erkannt.</p>";
    }

    // Opportunities
    const og = $("#opps-grid");
    og.innerHTML = "";
    (b.opportunities || []).forEach((o) => {
      const div = document.createElement("div");
      div.className = "opp";
      div.innerHTML = `
        <div class="opp-main">
          <h3>${escape(o.title)}</h3>
          <p class="what"><strong>Was</strong>${escape(o.what || "")}</p>
          <p class="who"><strong>Wer würde zahlen</strong>${escape(o.who || "")}</p>
        </div>
        <div class="opp-side">
          <div class="field">
            <span class="label">Umsetzbarkeit</span>
            <span class="value how ${howClass(o.how)}">${escape(o.how || "mittel")}</span>
          </div>
          <div class="field">
            <span class="label">Realistischer Preis</span>
            <span class="value price">${escape(o.price || "—")}</span>
          </div>
        </div>
      `;
      og.appendChild(div);
    });
    if (!b.opportunities || b.opportunities.length === 0) {
      og.innerHTML = "<p style='color: var(--ink-mute);'>Keine Opportunities erkannt.</p>";
    }

    // Top articles
    const al = $("#article-list");
    al.innerHTML = "";
    const articles = (b.top_articles && b.top_articles.length > 0)
      ? b.top_articles.map((a) => ({
          title: a.title,
          url: a.url,
          source: a.source,
          published: a.date,
          summary: a.why,
          keywords: a.tags || [],
        }))
      : (meta.raw_articles || []).slice(0, 8);
    articles.forEach((a) => {
      const div = document.createElement("div");
      div.className = "article";
      const tags = (a.keywords || []).slice(0, 4)
        .map((k) => `<span class="tag">${escape(k)}</span>`).join("");
      div.innerHTML = `
        <div class="date">${fmtShortDate(a.published)}</div>
        <div>
          <h4><a href="${escape(a.url)}" target="_blank" rel="noopener">${escape(a.title)}</a></h4>
          <div class="meta">${escape(a.source || "")} ${tags}</div>
          <p class="why">${escape(a.summary || "")}</p>
        </div>
      `;
      al.appendChild(div);
    });
    if (!articles.length) {
      al.innerHTML = "<p style='color: var(--ink-mute);'>Keine Artikel verfügbar.</p>";
    }

    // Action items
    const actionsOl = $("#actions-list");
    actionsOl.innerHTML = "";
    (b.action_items || []).forEach((a) => {
      const li = document.createElement("li");
      li.textContent = a;
      actionsOl.appendChild(li);
    });

    // Footer
    $("#footer-vertical").textContent = data.vertical || "—";
    $("#footer-build").textContent = `Generated ${fmtDate(meta.generated_at)}`;
  }

  function getISOWeek(d) {
    const date = new Date(d.getTime());
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
    const week1 = new Date(date.getFullYear(), 0, 4);
    return 1 + Math.round(((date - week1) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7);
  }

  // ── Archive drawer ─────────────────────────────────────────────
  // Loads web/data/archive/index.json (idempotent — once per page load)
  // and wires up the "Frühere Ausgaben" button in the hero. The archive
  // can grow to many entries, so we paginate the drawer 10 at a time
  // and show a "Mehr laden" button if there's more.
  const ARCHIVE_PAGE_SIZE = 10;

  function showError(msg) {
    document.querySelector("#headline").textContent = "Fehler beim Laden";
    document.querySelector("#subheadline").textContent = msg;
    document.querySelector("#exec-summary").innerHTML =
      `<p style='color: var(--signal-high);'>${escape(msg)}</p>`;
  }

  async function loadArchive() {
    const btn = document.querySelector("#archive-toggle");
    const drawer = document.querySelector("#archive-drawer");
    const list = document.querySelector("#archive-list");
    if (!btn || !drawer || !list) return;

    let index = { editions: [] };
    try {
      const res = await fetch("data/archive/index.json", { cache: "no-store" });
      if (res.ok) index = await res.json();
    } catch (e) {
      return;  // no archive yet — silently keep the drawer empty
    }

    if (!index.editions || index.editions.length === 0) {
      list.innerHTML = "<p class='archive-empty'>Noch keine früheren Ausgaben.</p>";
      return;
    }

    // Update button meta with count
    const meta = document.querySelector("#archive-toggle-meta");
    if (meta) meta.textContent = `(${index.editions.length})`;

    let shown = 0;
    const renderNextBatch = () => {
      const next = index.editions.slice(shown, shown + ARCHIVE_PAGE_SIZE);
      next.forEach((ed) => list.appendChild(buildArchiveItem(ed)));
      shown += next.length;
      // Remove existing "more" button if present
      const existingMore = list.querySelector(".archive-more");
      if (existingMore) existingMore.remove();
      if (shown < index.editions.length) {
        const more = document.createElement("button");
        more.className = "archive-more";
        more.type = "button";
        more.textContent = `Ältere Ausgaben laden (${index.editions.length - shown} weitere)`;
        more.addEventListener("click", () => renderNextBatch());
        list.appendChild(more);
      }
    };

    list.innerHTML = "";
    renderNextBatch();

    btn.addEventListener("click", () => {
      drawer.classList.toggle("open");
      btn.classList.toggle("open");
    });
  }

  function buildArchiveItem(ed) {
    const a = document.createElement("a");
    a.className = "archive-item";
    a.href = `data/archive/${ed.id}.json`;
    a.dataset.editionId = ed.id;
    const dt = new Date(ed.date || ed.generated_at);
    const dateStr = dt.toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" });
    a.innerHTML = `
      <span class="archive-date">${escape(dateStr)}</span>
      <span class="archive-headline">${escape(ed.headline || "—")}</span>
      <span class="archive-meta">${ed.article_count || 0} Art.</span>
    `;
    a.addEventListener("click", async (ev) => {
      ev.preventDefault();
      await loadEdition(`data/archive/${ed.id}.json`, a);
    });
    return a;
  }

  async function loadEdition(url, linkEl) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      renderBrief(data);
      document.querySelectorAll(".archive-item").forEach(el => el.classList.remove("active"));
      if (linkEl) linkEl.classList.add("active");
      const byline = document.querySelector("#byline-date");
      if (byline && data.generated_at) {
        byline.textContent = new Date(data.generated_at).toLocaleDateString("de-DE", { day: "2-digit", month: "short", year: "numeric" });
      }
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      showError(`Konnte die Ausgabe nicht laden: ${e.message}`);
    }
  }

  // Boot
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderBrief(data);
  } catch (e) {
    showError(`Konnte die aktuelle Ausgabe nicht laden: ${e.message}. Bitte später erneut versuchen.`);
    console.error(e);
  }
})();
