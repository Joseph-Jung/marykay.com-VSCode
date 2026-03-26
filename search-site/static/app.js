/* ── Mary Kay Search — Frontend Logic ─────────────────── */

const API = "/api";
let currentQuery = "";
let currentLocale = null;
let currentCategory = null;
let currentPageType = null;
let currentPage = 1;
let debounceTimer = null;
let searchMode = "keyword"; // "keyword" or "ai"

/* ── DOM References ──────────────────────────────────── */
const searchInput = document.getElementById("search-input");
const resultsGrid = document.getElementById("results-grid");
const resultsCount = document.getElementById("results-count");
const paginationEl = document.getElementById("pagination");
const categoriesEl = document.getElementById("categories-list");
const typesEl = document.getElementById("types-list");
const detailOverlay = document.getElementById("detail-overlay");
const detailContent = document.getElementById("detail-content");
const loadingEl = document.getElementById("loading");
const aiAnswerBox = document.getElementById("ai-answer-box");
const aiAnswerText = document.getElementById("ai-answer-text");
const aiSourcesEl = document.getElementById("ai-sources");

/* ── Initialize ──────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  searchInput.addEventListener("input", onSearchInput);
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });
  document.getElementById("search-btn").addEventListener("click", doSearch);
  detailOverlay.addEventListener("click", (e) => {
    if (e.target === detailOverlay) closeDetail();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDetail();
  });

  // Search mode toggle
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      searchMode = btn.dataset.mode;
      document.querySelectorAll(".mode-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      // Update placeholder
      if (searchMode === "ai") {
        searchInput.placeholder = "Ask a question about Mary Kay products...";
        document.querySelector(".sidebar").style.display = "none";
      } else {
        searchInput.placeholder = "Search products, skincare, makeup, fragrance...";
        document.querySelector(".sidebar").style.display = "";
      }
      aiAnswerBox.style.display = "none";
      currentPage = 1;
      if (searchInput.value.trim()) doSearch();
    });
  });

  // Locale buttons
  document.querySelectorAll(".locale-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const loc = btn.dataset.locale;
      if (currentLocale === loc) {
        currentLocale = null;
        document.querySelectorAll(".locale-btn").forEach(b => b.classList.remove("active"));
      } else {
        currentLocale = loc;
        document.querySelectorAll(".locale-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
      }
      currentPage = 1;
      doSearch();
    });
  });

  // Initial load — show all products
  doSearch();
});

/* ── Search ──────────────────────────────────────────── */
function onSearchInput() {
  // Only debounce-search for keyword mode; AI mode waits for Enter/click
  if (searchMode === "ai") return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    currentPage = 1;
    doSearch();
  }, 300);
}

async function doSearch() {
  currentQuery = searchInput.value.trim();

  if (searchMode === "ai") {
    await doAiSearch();
  } else {
    await doKeywordSearch();
  }
}

async function doKeywordSearch() {
  showLoading(true);
  aiAnswerBox.style.display = "none";

  const params = new URLSearchParams();
  params.set("q", currentQuery);
  params.set("page", currentPage);
  if (currentLocale) params.set("locale", currentLocale);
  if (currentCategory) params.set("category", currentCategory);
  if (currentPageType) params.set("page_type", currentPageType);

  try {
    const resp = await fetch(`${API}/search?${params}`);
    const data = await resp.json();
    renderResults(data);
    renderPagination(data);
    renderFacets(data.facets);
  } catch (err) {
    resultsGrid.innerHTML = `<div class="empty-state"><h3>Search Error</h3><p>${err.message}</p></div>`;
  }
  showLoading(false);
}

async function doAiSearch() {
  if (!currentQuery) {
    aiAnswerBox.style.display = "none";
    resultsGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1"><h3>Ask a question</h3><p>Type a natural language question about Mary Kay products.</p></div>`;
    resultsCount.innerHTML = "";
    paginationEl.innerHTML = "";
    return;
  }

  showLoading(true);
  resultsGrid.innerHTML = "";
  paginationEl.innerHTML = "";

  try {
    const resp = await fetch(`${API}/ai-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: currentQuery }),
    });
    const data = await resp.json();

    // Show AI answer
    aiAnswerBox.style.display = "block";
    aiAnswerText.innerHTML = formatAiAnswer(data.answer);

    // Show source products as card grid (replacing pills)
    aiSourcesEl.innerHTML = "";
    if (data.sources && data.sources.length > 0) {
      resultsCount.innerHTML = `<strong>${data.sources.length}</strong> related results`;
      resultsGrid.innerHTML = data.sources.map(s =>
        renderProductCard(s, currentQuery)
      ).join("");
    } else {
      resultsCount.innerHTML = "";
      resultsGrid.innerHTML = "";
    }
  } catch (err) {
    aiAnswerBox.style.display = "block";
    aiAnswerText.innerHTML = `<span style="color:var(--gray-400)">Error: ${escapeHtml(err.message)}</span>`;
    aiSourcesEl.innerHTML = "";
    resultsCount.innerHTML = "";
  }
  showLoading(false);
}

function formatAiAnswer(text) {
  if (!text) return "";
  // Extract markdown links before escaping, replace with placeholders
  const links = [];
  let processed = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, linkText, url) => {
    let fullUrl = url;
    if (url.startsWith("/")) fullUrl = "https://www.marykay.com" + url;
    else if (!url.startsWith("http")) fullUrl = "https://www.marykay.com/" + url;
    const idx = links.length;
    links.push(`<a href="${escapeHtml(fullUrl)}" target="_blank" rel="noopener">${escapeHtml(linkText)}</a>`);
    return `__LINK_${idx}__`;
  });
  // Now escape the rest
  let html = escapeHtml(processed);
  // Restore link placeholders
  links.forEach((link, i) => {
    html = html.replace(`__LINK_${i}__`, link);
  });
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Line breaks
  html = html.replace(/\n/g, "<br>");
  return html;
}

/* ── Shared Card Renderer ────────────────────────────── */
function renderProductCard(r, query) {
  // FAQ card — distinct layout without image/price
  if (r.page_type === "faq") {
    const faqTitle = escapeHtml(r.product_name || r.title || "");
    const faqSnippet = r.snippet || r.main_text || r.description || "";
    const displaySnippet = query ? highlightTerms(faqSnippet, query) : escapeHtml(faqSnippet);
    return `
      <div class="product-card faq-card" onclick="window.open('${escapeHtml(r.url)}', '_blank')">
        <div class="card-image-wrap">
          <div class="card-faq-icon">&#x2753;</div>
          <span class="card-badge badge-faq">FAQ</span>
        </div>
        <div class="card-body">
          <div class="card-category">${escapeHtml(r.category || "")}</div>
          <div class="card-title">${faqTitle}</div>
          <div class="card-snippet">${displaySnippet}</div>
        </div>
      </div>`;
  }

  const badgeClass = r.page_type === "product" ? "badge-product" :
                     r.page_type === "content" ? "badge-content" : "badge-category";

  const imgSrc = r.image_url || "";
  const imgAlt = r.image_alt || r.product_name || r.title || "";
  const imageHtml = imgSrc
    ? `<img class="card-image" src="${resize(imgSrc, 400)}" alt="${escapeHtml(imgAlt)}" loading="lazy" onerror="this.parentElement.innerHTML='<div class=card-image-placeholder>&#x1f48e;</div>'">`
    : `<div class="card-image-placeholder">&#x1f48e;</div>`;

  const snippetText = r.snippet || r.meta_description || r.description || (r.main_text || "").substring(0, 200);
  const displaySnippet = query ? highlightTerms(snippetText, query) : escapeHtml(snippetText);
  const name = r.product_name || r.h1 || r.title;

  const clickAction = r.content_hash
    ? `onclick="openDetail('${r.content_hash}')"`
    : `onclick="window.open('${escapeHtml(r.url)}', '_blank')"`;

  const footerHtml = r.confidence
    ? `<div class="card-footer">
        <span><span class="confidence-dot confidence-${r.confidence}"></span>${r.confidence}</span>
        <span>${r.locale === "es_US" ? "ES" : "EN"}</span>
      </div>`
    : "";

  return `
    <div class="product-card" ${clickAction}>
      <div class="card-image-wrap">
        ${imageHtml}
        <span class="card-badge ${badgeClass}">${r.page_type || "product"}</span>
      </div>
      <div class="card-body">
        <div class="card-category">${escapeHtml(r.category || "")}</div>
        <div class="card-title">${escapeHtml(name)}</div>
        ${r.price ? `<div class="card-price">${escapeHtml(r.price)}</div>` : ""}
        <div class="card-snippet">${displaySnippet}</div>
      </div>
      ${footerHtml}
    </div>`;
}

/* ── Render Results ──────────────────────────────────── */
function renderResults(data) {
  const { results, total_results, query } = data;

  if (query) {
    resultsCount.innerHTML = `<strong>${total_results}</strong> results for "<strong>${escapeHtml(query)}</strong>"`;
  } else {
    resultsCount.innerHTML = `Showing <strong>${total_results}</strong> items`;
  }

  if (results.length === 0) {
    resultsGrid.innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <h3>No results found</h3>
        <p>Try a different search term, or browse by category.</p>
      </div>`;
    return;
  }

  resultsGrid.innerHTML = results.map((r) => renderProductCard(r, query)).join("");
}

/* ── Render Facets ───────────────────────────────────── */
function renderFacets(facets) {
  if (!facets) return;

  // Categories
  if (facets.categories && categoriesEl) {
    categoriesEl.innerHTML = facets.categories.slice(0, 10).map((c) => `
      <label class="filter-option">
        <input type="radio" name="category" value="${escapeHtml(c.name)}"
          ${currentCategory === c.name ? "checked" : ""}
          onchange="setCategory(this.value)">
        ${escapeHtml(c.name)}
        <span class="filter-count">${c.count}</span>
      </label>
    `).join("") + `<button class="filter-clear" onclick="clearCategory()">Clear</button>`;
  }

  // Page types
  if (facets.page_types && typesEl) {
    typesEl.innerHTML = facets.page_types.map((t) => `
      <label class="filter-option">
        <input type="radio" name="page_type" value="${t.name}"
          ${currentPageType === t.name ? "checked" : ""}
          onchange="setPageType(this.value)">
        ${t.name.charAt(0).toUpperCase() + t.name.slice(1)}
        <span class="filter-count">${t.count}</span>
      </label>
    `).join("") + `<button class="filter-clear" onclick="clearPageType()">Clear</button>`;
  }
}

/* ── Filter Actions ──────────────────────────────────── */
function setCategory(cat) {
  currentCategory = cat;
  currentPage = 1;
  doSearch();
}

function clearCategory() {
  currentCategory = null;
  currentPage = 1;
  doSearch();
}

function setPageType(type) {
  currentPageType = type;
  currentPage = 1;
  doSearch();
}

function clearPageType() {
  currentPageType = null;
  currentPage = 1;
  doSearch();
}

/* ── Pagination ──────────────────────────────────────── */
function renderPagination(data) {
  const { page, total_pages } = data;
  if (total_pages <= 1) { paginationEl.innerHTML = ""; return; }

  let html = "";
  html += `<button class="page-btn" ${page <= 1 ? "disabled" : ""} onclick="goPage(${page - 1})">&laquo;</button>`;

  const start = Math.max(1, page - 2);
  const end = Math.min(total_pages, page + 2);

  if (start > 1) html += `<button class="page-btn" onclick="goPage(1)">1</button>`;
  if (start > 2) html += `<span style="color:var(--gray-400)">...</span>`;

  for (let i = start; i <= end; i++) {
    html += `<button class="page-btn ${i === page ? "active" : ""}" onclick="goPage(${i})">${i}</button>`;
  }

  if (end < total_pages - 1) html += `<span style="color:var(--gray-400)">...</span>`;
  if (end < total_pages) html += `<button class="page-btn" onclick="goPage(${total_pages})">${total_pages}</button>`;

  html += `<button class="page-btn" ${page >= total_pages ? "disabled" : ""} onclick="goPage(${page + 1})">&raquo;</button>`;

  paginationEl.innerHTML = html;
}

function goPage(p) {
  currentPage = p;
  doSearch();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ── Product Detail ──────────────────────────────────── */
async function openDetail(hash) {
  detailOverlay.classList.add("active");
  detailContent.innerHTML = `<div class="loading"><div class="spinner"></div>Loading...</div>`;

  try {
    const resp = await fetch(`${API}/product/${hash}`);
    const p = await resp.json();

    if (p.error) {
      detailContent.innerHTML = `<div class="empty-state"><h3>Not Found</h3></div>`;
      return;
    }

    const imageHtml = p.image && p.image.src
      ? `<img class="detail-image" src="${resize(p.image.src, 800)}" alt="${escapeHtml(p.image.alt)}">`
      : `<div class="card-image-placeholder" style="font-size:80px">&#x1f48e;</div>`;

    const breadcrumbHtml = p.breadcrumbs.length
      ? `<div class="detail-breadcrumbs">${p.breadcrumbs.map(escapeHtml).join(" &rsaquo; ")}</div>`
      : `<div class="detail-breadcrumbs">${escapeHtml(p.category)}</div>`;

    const sourceUrl = p.canonical_url && p.canonical_url.startsWith("http")
      ? p.canonical_url : p.url;

    // Build product fields sections
    const pf = p.product_fields || {};
    let sectionsHtml = "";

    // Description / main text (first 1000 chars)
    const descText = p.main_text ? p.main_text.substring(0, 1500) : "";
    if (descText) {
      sectionsHtml += buildSection("Description", `<p>${escapeHtml(descText)}</p>`);
    }

    // Key Benefits
    if (pf.key_benefits && pf.key_benefits.length) {
      sectionsHtml += buildSection("Key Benefits",
        `<ul>${pf.key_benefits.map(b => `<li>${escapeHtml(b)}</li>`).join("")}</ul>`);
    }

    // How to Use
    if (pf.how_to_use) {
      sectionsHtml += buildSection("How to Use", `<p>${escapeHtml(pf.how_to_use)}</p>`);
    }

    // Ingredients
    if (pf.ingredients && pf.ingredients.length) {
      sectionsHtml += buildSection("Ingredients",
        `<p>${pf.ingredients.map(escapeHtml).join(", ")}</p>`);
    }

    // Warnings
    if (pf.warnings) {
      sectionsHtml += buildSection("Warnings", `<p>${escapeHtml(pf.warnings)}</p>`);
    }

    // FAQ
    if (p.faq_pairs && p.faq_pairs.length) {
      const faqHtml = p.faq_pairs
        .filter(fq => fq.question && fq.answer && fq.question !== "Required")
        .slice(0, 10)
        .map(fq => `
          <div class="faq-item">
            <div class="faq-q">${escapeHtml(fq.question)}</div>
            <div class="faq-a">${escapeHtml(fq.answer)}</div>
          </div>
        `).join("");
      if (faqHtml) {
        sectionsHtml += buildSection(`FAQ (${p.faq_pairs.length})`, faqHtml);
      }
    }

    detailContent.innerHTML = `
      <div class="detail-panel">
        <div class="detail-top">
          <button class="detail-close" onclick="closeDetail()">&times;</button>
          <div class="detail-image-wrap">${imageHtml}</div>
          <div class="detail-info">
            ${breadcrumbHtml}
            <h2 class="detail-title">${escapeHtml(p.h1 || p.title)}</h2>
            ${p.price ? `<div class="detail-price">${escapeHtml(p.price)}</div>` : ""}
            <p class="detail-meta">${escapeHtml(p.meta_description)}</p>
            ${pf.size ? `<p class="detail-meta"><strong>Size:</strong> ${escapeHtml(pf.size)}</p>` : ""}
            <a class="detail-source" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener">
              View on marykay.com &rarr;
            </a>
          </div>
        </div>
        <div class="detail-sections">${sectionsHtml}</div>
      </div>`;
  } catch (err) {
    detailContent.innerHTML = `<div class="empty-state"><h3>Error loading details</h3><p>${err.message}</p></div>`;
  }
}

function closeDetail() {
  detailOverlay.classList.remove("active");
}

function buildSection(title, content) {
  return `
    <div class="detail-section">
      <div class="section-title" onclick="toggleSection(this)">${title}</div>
      <div class="section-content">${content}</div>
    </div>`;
}

function toggleSection(el) {
  el.classList.toggle("collapsed");
  const content = el.nextElementSibling;
  content.classList.toggle("hidden");
}

/* ── Utilities ───────────────────────────────────────── */
function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function resize(url, size) {
  // Adjust Demandware image size params
  if (url.includes("sw=") || url.includes("sh=")) {
    return url.replace(/sw=\d+/, `sw=${size}`).replace(/sh=\d+/, `sh=${size}`);
  }
  if (url.includes("?")) return url + `&sw=${size}&sh=${size}&sm=fit`;
  return url + `?sw=${size}&sh=${size}&sm=fit`;
}

function highlightTerms(text, query) {
  if (!text || !query) return escapeHtml(text || "");
  const escaped = escapeHtml(text);
  const terms = query.toLowerCase().split(/\s+/).filter(t => t.length > 1);
  let result = escaped;
  terms.forEach(term => {
    const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    result = result.replace(regex, "<mark>$1</mark>");
  });
  return result;
}

function showLoading(show) {
  loadingEl.style.display = show ? "block" : "none";
  if (show) resultsGrid.style.opacity = "0.4";
  else resultsGrid.style.opacity = "1";
}
