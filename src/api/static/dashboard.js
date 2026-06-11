const REFRESH_MS = 30000;

let refreshTimer = null;
let lastData = null;

const loginView = document.getElementById("login-view");
const appView = document.getElementById("app-view");
const errorBanner = document.getElementById("error-banner");
const successBanner = document.getElementById("success-banner");
const loginError = document.getElementById("login-error");

try { localStorage.removeItem("divap_api_key"); } catch (_) {}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.classList.add("show");
}

function hideError() {
  errorBanner.classList.remove("show");
}

function showSuccess(msg) {
  successBanner.textContent = msg;
  successBanner.classList.add("show");
  setTimeout(() => successBanner.classList.remove("show"), 5000);
}

function showLoginError(msg) {
  if (!loginError) return;
  loginError.textContent = msg;
  loginError.classList.add("show");
}

function hideLoginError() {
  if (!loginError) return;
  loginError.classList.remove("show");
}

function buildQuery() {
  const params = new URLSearchParams();
  params.set("limit", "30");
  const symbol = document.getElementById("filter-symbol")?.value;
  const tf = document.getElementById("filter-tf")?.value;
  const conf = document.getElementById("filter-conf")?.value;
  const last24 = document.getElementById("filter-24h")?.checked;
  if (symbol) params.set("symbol", symbol);
  if (tf) params.set("timeframe", tf);
  if (conf) params.set("confidence", conf);
  if (last24) params.set("hours", "24");
  return params.toString();
}

async function fetchDashboard() {
  const res = await fetch(`/dashboard/data?${buildQuery()}`, { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || body.error || `Erro ${res.status}`);
  }
  return body;
}

async function fetchMarket() {
  const res = await fetch("/dashboard/market", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return null;
  return body.data || null;
}

async function fetchBalance() {
  const res = await fetch("/dashboard/balance", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return null;
  return body.data || null;
}

async function login(secret) {
  const res = await fetch("/dashboard/auth", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || "Chave inválida");
}

async function logoutSession() {
  await fetch("/dashboard/logout", { method: "POST", credentials: "same-origin" });
}

function fmtNum(val, digits = 2) {
  if (val == null || val === "") return "—";
  const n = Number(val);
  if (Number.isNaN(n)) return val;
  return n.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function fmtDuration(seconds) {
  if (seconds == null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}min`;
  }
  if (m > 0) return `${m} min`;
  return `${s}s`;
}

function dirLabel(d) {
  return d === "buy" ? '<span class="tag-buy">Compra</span>' : '<span class="tag-sell">Venda</span>';
}

function confLabel(c) {
  if (c === "high") return '<span class="tag-high">Alta</span>';
  if (c === "medium") return '<span class="tag-medium">Média</span>';
  return c || "—";
}

function verdictLabel(v) {
  if (!v) return "—";
  const map = { confirm: "Confirm", caution: "Caution", reject: "Reject", unknown: "—" };
  const cls = v === "confirm" ? "tag-verdict-confirm" : v === "caution" ? "tag-verdict-caution" : v === "reject" ? "tag-verdict-reject" : "";
  return `<span class="${cls}">${map[v] || v}</span>`;
}

function htfLabel(d1, w1) {
  const short = (t) => {
    if (!t) return "—";
    const m = { bullish: "↑", bearish: "↓", sideways: "→", unknown: "?" };
    return m[t] || t.slice(0, 3);
  };
  return `${short(d1)}/${short(w1)}`;
}

function execBadge(reason) {
  if (!reason) return "";
  const cls = reason.includes("Elegível") ? "ok" : reason.includes("média") || reason.includes("Aguardando") || reason.includes("Gate") ? "block" : "";
  return `<span class="exec-badge ${cls}" title="${reason}">${reason}</span>`;
}

function statusLabel(s) {
  const map = { open: "Aberto", closed: "Fechado", simulated: "Simulado" };
  return map[s] || s || "—";
}

function drawMiniChart(canvas, entry, stop, targets) {
  if (!canvas || entry == null) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const prices = [Number(stop), Number(entry), ...(targets || []).map(Number)].filter((n) => !Number.isNaN(n));
  if (prices.length < 2) return;
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const y = (p) => h - 4 - ((p - min) / range) * (h - 8);

  ctx.strokeStyle = "#333";
  ctx.beginPath();
  ctx.moveTo(4, y(entry));
  ctx.lineTo(w - 4, y(entry));
  ctx.stroke();

  if (stop != null) {
    ctx.strokeStyle = "#ef4444";
    ctx.setLineDash([3, 2]);
    ctx.beginPath();
    ctx.moveTo(4, y(stop));
    ctx.lineTo(w - 4, y(stop));
    ctx.stroke();
    ctx.setLineDash([]);
  }

  (targets || []).forEach((tp, i) => {
    ctx.strokeStyle = i === 0 ? "#22c55e" : "#16a34a88";
    ctx.beginPath();
    ctx.moveTo(4, y(tp));
    ctx.lineTo(w - 4, y(tp));
    ctx.stroke();
  });

  ctx.fillStyle = "#3b82f6";
  ctx.beginPath();
  ctx.arc(w / 2, y(entry), 3, 0, Math.PI * 2);
  ctx.fill();
}

function renderBadges(health, stats, scan) {
  const el = document.getElementById("status-badges");
  const online = health?.status === "ok";
  const testnet = stats?.trading_mode === "testnet";
  const trading = stats?.trading_enabled;
  const beat = scan?.beat_active;
  const beatTitle = beat
    ? `Beat ativo · visto há ${fmtDuration(scan?.beat_seconds_since ?? 0)}`
    : scan?.beat_seconds_since != null
      ? `Beat inativo · último sinal há ${fmtDuration(scan.beat_seconds_since)}`
      : "Beat ainda sem heartbeat — aguarde ~1 min após deploy";
  el.innerHTML = `
    <span class="badge ${online ? "ok" : "off"}">${online ? "● Online" : "○ Offline"}</span>
    <span class="badge ${testnet ? "warn" : ""}">${testnet ? "Testnet" : stats?.trading_mode || "—"}</span>
    <span class="badge ${trading ? "ok" : "off"}">Trading ${trading ? "ON" : "OFF"}</span>
    <span class="badge ${beat ? "ok beat-pulse" : "off"}" title="${beatTitle.replace(/"/g, "&quot;")}">${beat ? "● Beat ativo" : "○ Beat inativo"}</span>
  `;
}

function renderTradingReadinessLoading() {
  const panel = document.getElementById("trading-readiness-panel");
  if (panel) {
    panel.innerHTML = '<div class="empty">Verificando pipeline testnet…</div>';
  }
}

function renderTradingReadiness(readiness) {
  const panel = document.getElementById("trading-readiness-panel");
  if (!panel) return;
  const r = readiness || {};
  const checks = r.checks || [];
  if (!checks.length) {
    panel.innerHTML = '<div class="empty">Carregando validação…</div>';
    return;
  }
  const list = checks.map((c) => `
    <li class="readiness-item ${c.ok ? "ok" : "fail"}">
      <span class="readiness-icon">${c.ok ? "✓" : "✗"}</span>
      <div>
        <strong>${c.label}</strong>
        ${c.detail ? `<div class="readiness-detail">${c.detail}</div>` : ""}
      </div>
    </li>`).join("");
  const perf = r.profile_performance || [];
  const perfHtml = perf.length
    ? `<div class="readiness-perf">${perf.map((p) =>
        `<span>${p.name}: ${(p.closed_count ?? 0) + (p.open_count ?? 0)} trades</span>`
      ).join("")}</div>`
    : "";
  panel.innerHTML = `
    <div class="readiness-header ${r.ready ? "ready" : "pending"}">
      ${r.ready ? "Pronto para operar na testnet" : "Ajustes necessários"}
    </div>
    <ul class="readiness-list">${list}</ul>
    ${perfHtml}
    <p class="readiness-hint">${r.hint || ""}</p>
  `;
}

async function fetchTradingReadiness() {
  const res = await fetch("/dashboard/trading-readiness", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return null;
  return body.data || null;
}

async function fetchStrategyInsights() {
  const res = await fetch("/dashboard/strategy/insights", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return null;
  return body.data || null;
}

async function fetchStrategy() {
  const res = await fetch("/dashboard/strategy", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return null;
  return body.data || null;
}

async function saveBankroll(activeProfileId, monthlyTarget) {
  const payload = {};
  if (activeProfileId) payload.active_profile_id = activeProfileId;
  if (monthlyTarget !== null && monthlyTarget !== "") payload.monthly_target_usdt = Number(monthlyTarget);
  const res = await fetch("/dashboard/bankroll", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || "Falha ao salvar banca");
  return body.data;
}

function profileFitClass(status) {
  return `fit-${status || "neutro"}`;
}

function profileLabel(id) {
  const map = {
    divap: "DIVAP",
    conservador: "Conservador",
    caixa_rapido: "Caixa rápido",
    agressivo: "Agressivo",
  };
  return map[id] || id || "—";
}

function renderProfiles(data, insightsMap) {
  const profiles = data?.profiles || [];
  const grid = document.getElementById("profiles-grid");
  if (!profiles.length) {
    grid.innerHTML = '<div class="empty">Carregando perfis…</div>';
    return;
  }
  grid.innerHTML = profiles.map((p) => {
    const perf = p.performance;
    const ai = insightsMap?.[p.id] || p.ai_insight;
    const perfHtml = perf ? `
      <div class="profile-stats">
        <div><span>PnL mês</span><strong>${fmtNum(perf.month_pnl_usdt)}</strong></div>
        <div><span>Win rate</span><strong>${fmtNum(perf.win_rate_pct, 1)}%</strong></div>
        <div><span>Fechados</span><strong>${perf.closed_count ?? 0}</strong></div>
        <div><span>PnL total</span><strong>${fmtNum(perf.total_pnl_usdt)}</strong></div>
      </div>` : "";
    const aiHtml = ai
      ? `<div class="profile-ai-insight"><strong>IA:</strong> ${ai.replace(/</g, "&lt;")}</div>`
      : "";
    return `
    <div class="profile-card ${p.is_active ? "active" : ""}">
      ${p.is_active ? '<span class="active-pill">Ativo na execução</span>' : ""}
      <div class="profile-name">${p.name}</div>
      <div class="profile-tagline">${p.tagline || ""}</div>
      <div class="fit-score ${profileFitClass(p.status)}">${p.fit_score}%</div>
      <div class="profile-headline">${p.headline || ""}</div>
      <div class="profile-detail">${p.detail || ""}</div>
      ${aiHtml}
      ${perfHtml}
    </div>`;
  }).join("");
}

function renderProfilePerformance(data) {
  const perf = data?.performance || [];
  const grid = document.getElementById("profile-performance-grid");
  if (!grid) return;
  if (!perf.length) {
    grid.innerHTML = '<div class="empty">Sem trades executados por perfil ainda.</div>';
    return;
  }
  grid.innerHTML = perf.map((p) => `
    <div class="profile-card ${p.profile_id === data.active_profile_id ? "active" : ""}">
      <div class="profile-name">${p.name}</div>
      <div class="profile-stats">
        <div><span>Semana</span><strong>${fmtNum(p.week_pnl_usdt)} USDT</strong></div>
        <div><span>Mês</span><strong>${fmtNum(p.month_pnl_usdt)} USDT</strong></div>
        <div><span>Total</span><strong>${fmtNum(p.total_pnl_usdt)} USDT</strong></div>
        <div><span>Win rate</span><strong>${fmtNum(p.win_rate_pct, 1)}%</strong></div>
      </div>
      <div class="profile-detail">${p.closed_count ?? 0} fechados · ${p.open_count ?? 0} abertos</div>
    </div>
  `).join("");
}

function renderProfileHistory(data) {
  const history = data?.history || {};
  const profiles = data?.profiles || [];
  const container = document.getElementById("profile-history-tabs");
  if (!container) return;
  const blocks = profiles.map((p) => {
    const rows = history[p.id] || [];
    if (!rows.length) {
      return `<div class="profile-history-block"><h3>${p.name}</h3><div class="empty">Nenhum trade neste perfil</div></div>`;
    }
    const body = rows.map((t) => `
      <tr>
        <td>#${t.id}</td>
        <td>${t.symbol}</td>
        <td>${t.timeframe}</td>
        <td>${statusLabel(t.status)}</td>
        <td>${t.pnl_usdt != null ? fmtNum(t.pnl_usdt) : "—"}</td>
        <td>${t.goal_protected ? "Protegido" : "—"}</td>
      </tr>`).join("");
    return `<div class="profile-history-block"><h3>${p.name}</h3>
      <table><thead><tr><th>ID</th><th>Par</th><th>TF</th><th>Status</th><th>PnL</th><th>Modo</th></tr></thead><tbody>${body}</tbody></table>
    </div>`;
  }).join("");
  container.innerHTML = blocks || '<div class="empty">Sem histórico por perfil.</div>';
}

function renderBankroll(bankroll, profilesPayload) {
  const b = bankroll || {};
  const select = document.getElementById("active-profile-select");
  const targetInput = document.getElementById("monthly-target-input");
  if (select && b.active_profile_id) select.value = b.active_profile_id;
  if (targetInput && b.monthly_target_usdt != null) targetInput.value = b.monthly_target_usdt;

  const progress = b.progress_pct != null ? Math.min(100, Number(b.progress_pct)) : 0;
  const summary = document.getElementById("bankroll-summary");
  summary.innerHTML = `
    <div class="bankroll-grid">
      <div class="bankroll-stat"><div class="label">PnL mês</div><div class="value">${fmtNum(b.monthly_pnl_usdt)} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Meta mensal</div><div class="value">${b.monthly_target_usdt ? fmtNum(b.monthly_target_usdt) + " USDT" : "—"}</div></div>
      <div class="bankroll-stat"><div class="label">PnL semana</div><div class="value">${fmtNum(b.weekly_pnl_usdt)} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Meta semanal*</div><div class="value">${b.weekly_target_usdt ? fmtNum(b.weekly_target_usdt) : "—"} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Falta p/ meta (sem.)</div><div class="value">${b.weekly_needed_usdt ? fmtNum(b.weekly_needed_usdt) : "—"} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Banca demo</div><div class="value">${b.balance_usdt ? fmtNum(b.balance_usdt) : "—"} USDT</div></div>
    </div>
    ${b.monthly_target_usdt ? `<div class="progress-bar"><span style="width:${progress}%"></span></div><div class="subtitle">${progress}% da meta mensal</div>` : ""}
    ${b.protected_mode ? '<div class="protected-banner">Meta mensal atingida — modo protegido: só entradas DIVAP alta confiança + contexto confirm.</div>' : ""}
    <p class="subtitle" style="margin-top:0.5rem;">* Meta semanal = divisão proporcional da meta mensual pelas semanas do mês.</p>
  `;

  if (profilesPayload?.profiles) renderProfiles(profilesPayload, null);
  if (profilesPayload) {
    renderProfilePerformance(profilesPayload);
    renderProfileHistory(profilesPayload);
  }
}

async function loadTradingReadiness() {
  renderTradingReadinessLoading();
  try {
    const data = await fetchTradingReadiness();
    if (data) renderTradingReadiness(data);
  } catch (_) {
    const panel = document.getElementById("trading-readiness-panel");
    if (panel) panel.innerHTML = '<div class="empty">Não foi possível carregar validação testnet.</div>';
  }
}

async function loadProfileInsights(profilesPayload) {
  try {
    const data = await fetchStrategyInsights();
    if (data?.insights && profilesPayload) {
      renderProfiles(profilesPayload, data.insights);
    }
  } catch (_) {
    /* mantém texto rule-based */
  }
}

async function loadStrategyExtras() {
  try {
    const data = await fetchStrategy();
    if (!data) return;
    renderBankroll(data.bankroll, data.profiles);
    loadProfileInsights(data.profiles);
  } catch (_) {
    document.getElementById("profiles-grid").innerHTML =
      '<div class="empty">Não foi possível carregar perfis agora.</div>';
  }
}

function renderMarketPlaceholder() {
  document.getElementById("market-grid").innerHTML = `
    <div class="card"><div class="card-label">Fear & Greed</div><div class="card-value">…</div></div>
    <div class="card"><div class="card-label">Dominância BTC</div><div class="card-value">…</div></div>
    <div class="card"><div class="card-label">Mercado 24h</div><div class="card-value">…</div></div>
    <div class="card"><div class="card-label">Score médio</div><div class="card-value">…</div></div>
    <div class="card"><div class="card-label">Veredito dominante</div><div class="card-value">…</div></div>
  `;
}

function renderBalancePlaceholder(stats) {
  const d = stats || {};
  document.getElementById("stats-grid").innerHTML = `
    <div class="card highlight"><div class="card-label">USDT demo</div><div class="card-value">…</div><div class="card-sub">Carregando saldo</div></div>
    <div class="card"><div class="card-label">Win rate</div><div class="card-value">${fmtNum(d.win_rate_pct, 1)}%</div></div>
    <div class="card"><div class="card-label">PnL total</div><div class="card-value">${fmtNum(d.total_pnl_usdt)} USDT</div></div>
    <div class="card"><div class="card-label">Trades fechados</div><div class="card-value">${d.closed_count ?? 0}</div></div>
    <div class="card"><div class="card-label">Abertos</div><div class="card-value">${d.open_count ?? 0}</div></div>
    <div class="card"><div class="card-label">Vitórias / Derrotas</div><div class="card-value">${d.wins ?? 0} / ${d.losses ?? 0}</div></div>
    <div class="card"><div class="card-label">Taxas</div><div class="card-value">${fmtNum(d.total_fees_usdt)} USDT</div></div>
  `;
}

async function loadSlowExtras(stats) {
  renderMarketPlaceholder();
  renderBalancePlaceholder(stats);
  const [market, balance] = await Promise.all([fetchMarket(), fetchBalance()]);
  if (market) {
    renderMarket(market);
  } else {
    document.getElementById("market-grid").innerHTML =
      '<div class="empty">Mercado indisponível agora — tente Atualizar.</div>';
  }
  renderStats(stats, balance);
}

function renderMarket(market) {
  const m = market || {};
  document.getElementById("market-grid").innerHTML = `
    <div class="card"><div class="card-label">Fear & Greed</div><div class="card-value">${m.fear_greed ?? "—"}</div></div>
    <div class="card"><div class="card-label">Dominância BTC</div><div class="card-value">${m.btc_dominance_pct != null ? fmtNum(m.btc_dominance_pct, 1) + "%" : "—"}</div></div>
    <div class="card"><div class="card-label">Mercado 24h</div><div class="card-value ${Number(m.market_cap_change_24h_pct) >= 0 ? "positive" : "negative"}">${m.market_cap_change_24h_pct != null ? fmtNum(m.market_cap_change_24h_pct, 2) + "%" : "—"}</div></div>
    <div class="card"><div class="card-label">Score médio</div><div class="card-value">${m.avg_context_score ?? "—"}</div></div>
    <div class="card"><div class="card-label">Veredito dominante</div><div class="card-value">${verdictLabel(m.dominant_verdict)}</div></div>
  `;
}

function renderStats(stats, balance) {
  const d = stats || {};
  const pnl = Number(d.total_pnl_usdt || 0);
  const pnlClass = pnl > 0 ? "positive" : pnl < 0 ? "negative" : "";
  const bal = balance?.usdt_free;
  document.getElementById("stats-grid").innerHTML = `
    <div class="card highlight"><div class="card-label">USDT demo</div><div class="card-value">${bal != null ? fmtNum(bal) : "—"}</div><div class="card-sub">Saldo livre testnet</div></div>
    <div class="card"><div class="card-label">Win rate</div><div class="card-value">${fmtNum(d.win_rate_pct, 1)}%</div></div>
    <div class="card"><div class="card-label">PnL total</div><div class="card-value ${pnlClass}">${fmtNum(pnl)} USDT</div></div>
    <div class="card"><div class="card-label">Trades fechados</div><div class="card-value">${d.closed_count ?? 0}</div></div>
    <div class="card"><div class="card-label">Abertos</div><div class="card-value">${d.open_count ?? 0}</div></div>
    <div class="card"><div class="card-label">Vitórias / Derrotas</div><div class="card-value">${d.wins ?? 0} / ${d.losses ?? 0}</div></div>
    <div class="card"><div class="card-label">Taxas</div><div class="card-value">${fmtNum(d.total_fees_usdt)} USDT</div></div>
  `;
}

function renderScan(scan) {
  const s = scan || {};
  const since = s.seconds_since_last != null ? `há ${fmtDuration(s.seconds_since_last)}` : "nunca";
  const until = s.seconds_until_next != null ? `~${fmtDuration(s.seconds_until_next)}` : "—";
  const interval = s.interval_seconds ? Math.round(s.interval_seconds / 60) : 15;
  const beat = s.beat_active ? "beat OK" : "beat —";
  document.getElementById("scan-status").textContent =
    `Último scan: ${since} · próximo em ${until} · sinais: ${s.last_signals ?? 0} · automático a cada ${interval} min · ${beat}`;
}

function tradeRow(t, clickable = true) {
  const pnl = t.pnl_usdt != null ? Number(t.pnl_usdt) : null;
  const pnlHtml = pnl != null
    ? `<span class="${pnl >= 0 ? "tag-buy" : "tag-sell"}">${fmtNum(pnl)}</span>`
    : "—";
  return `<tr class="${clickable ? "clickable" : ""}" data-trade-id="${t.id}">
    <td>#${t.id}</td>
    <td>${t.symbol}</td>
    <td>${t.timeframe}</td>
    <td>${profileLabel(t.profile_id)}</td>
    <td>${dirLabel(t.direction)}</td>
    <td>${statusLabel(t.status)}</td>
    <td>${fmtNum(t.entry_price)}</td>
    <td>${pnlHtml}</td>
    <td>${t.trading_mode || "—"}</td>
    <td>${fmtDate(t.opened_at || t.created_at)}</td>
  </tr>`;
}

function renderOpenTrades(trades) {
  const rows = trades || [];
  const tbody = document.getElementById("open-trades-body");
  const section = document.getElementById("open-trades-section");
  if (!rows.length) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  tbody.innerHTML = rows.map((t) => tradeRow(t)).join("");
}

function renderTrades(trades) {
  const rows = trades || [];
  const tbody = document.getElementById("trades-body");
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="10" class="empty">Nenhum trade fechado ainda</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((t) => tradeRow(t)).join("");
}

function renderAlerts(alerts) {
  const rows = alerts || [];
  const tbody = document.getElementById("alerts-body");
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="13" class="empty">Nenhum alerta registrado</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((a) => {
    const targets = a.targets || [];
    return `<tr class="clickable" data-alert-id="${a.id}">
      <td>#${a.id}</td>
      <td>${a.symbol}</td>
      <td>${a.timeframe}</td>
      <td>${dirLabel(a.direction)}</td>
      <td>${confLabel(a.confidence)}</td>
      <td>${a.context_score ?? "—"}</td>
      <td>${verdictLabel(a.context_verdict)}</td>
      <td>${htfLabel(a.htf_1d, a.htf_1w)}</td>
      <td>${a.fear_greed ?? "—"}</td>
      <td>${execBadge(a.execution_reason)}</td>
      <td>${fmtNum(a.entry_price)}</td>
      <td><canvas class="mini-chart" width="72" height="28" data-entry="${a.entry_price}" data-stop="${a.stop_loss || ""}" data-targets='${JSON.stringify(targets)}'></canvas></td>
      <td>${fmtDate(a.created_at)}</td>
    </tr>`;
  }).join("");

  tbody.querySelectorAll(".mini-chart").forEach((canvas) => {
    let targets = [];
    try { targets = JSON.parse(canvas.dataset.targets || "[]"); } catch (_) {}
    drawMiniChart(canvas, canvas.dataset.entry, canvas.dataset.stop, targets);
  });
}

function renderPnlChart(series) {
  const wrap = document.getElementById("pnl-chart-section");
  const canvas = document.getElementById("pnl-chart");
  if (!series?.length) {
    wrap.classList.add("hidden");
    return;
  }
  wrap.classList.remove("hidden");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = 160 * dpr;
  canvas.style.width = rect.width + "px";
  canvas.style.height = "160px";
  ctx.scale(dpr, dpr);

  const w = rect.width;
  const h = 160;
  const values = series.map((p) => Number(p.cumulative_usdt));
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = max - min || 1;
  const xStep = w / Math.max(series.length - 1, 1);
  const y = (v) => h - 20 - ((v - min) / range) * (h - 40);

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = "#333";
  ctx.beginPath();
  ctx.moveTo(0, y(0));
  ctx.lineTo(w, y(0));
  ctx.stroke();

  ctx.strokeStyle = "#3b82f6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  series.forEach((p, i) => {
    const px = i * xStep;
    const py = y(Number(p.cumulative_usdt));
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();
}

function closeModal() {
  const el = document.getElementById("modal-root");
  if (el) el.innerHTML = "";
}

async function openAlertModal(alertId) {
  const res = await fetch(`/dashboard/alerts/${alertId}`, { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    showError(body.detail || "Falha ao carregar alerta");
    return;
  }
  const { alert, analysis } = body.data || {};
  const targets = (alert?.targets || []).map((t) => fmtNum(t)).join(", ") || "—";
  document.getElementById("modal-root").innerHTML = `
    <div class="modal-backdrop" id="modal-backdrop">
      <div class="modal" role="dialog">
        <header><h3>Alerta #${alert?.id} — ${alert?.symbol} ${alert?.timeframe}</h3></header>
        <dl>
          <dt>Lado</dt><dd>${alert?.direction === "buy" ? "Compra" : "Venda"}</dd>
          <dt>Confiança</dt><dd>${alert?.confidence}</dd>
          <dt>Score / Veredito</dt><dd>${alert?.context_score ?? "—"} / ${alert?.context_verdict ?? "—"}</dd>
          <dt>HTF 1d/1w</dt><dd>${alert?.htf_1d ?? "—"} / ${alert?.htf_1w ?? "—"}</dd>
          <dt>Fear & Greed</dt><dd>${alert?.fear_greed ?? "—"}</dd>
          <dt>Entrada / Stop</dt><dd>${fmtNum(alert?.entry_price)} / ${fmtNum(alert?.stop_loss)}</dd>
          <dt>Alvos</dt><dd>${targets}</dd>
          <dt>Execução</dt><dd>${alert?.execution_reason ?? "—"}</dd>
        </dl>
        <h4 style="font-size:0.85rem;color:var(--text-muted);margin-bottom:0.5rem;">Análise IA</h4>
        <div class="analysis-body">${analysis ? analysis.replace(/</g, "&lt;") : "Análise não disponível para este alerta."}</div>
        <div class="modal-actions">
          <button type="button" class="secondary" id="modal-close">Fechar</button>
        </div>
      </div>
    </div>`;
  document.getElementById("modal-close").onclick = closeModal;
  document.getElementById("modal-backdrop").onclick = (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
  };
}

async function openTradeModal(tradeId) {
  const res = await fetch(`/dashboard/trades/${tradeId}`, { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    showError(body.detail || "Falha ao carregar trade");
    return;
  }
  const { trade, alert_context: ctx } = body.data || {};
  document.getElementById("modal-root").innerHTML = `
    <div class="modal-backdrop" id="modal-backdrop">
      <div class="modal" role="dialog">
        <header><h3>Trade #${trade?.id} — ${trade?.symbol}</h3></header>
        <dl>
          <dt>Status</dt><dd>${statusLabel(trade?.status)}</dd>
          <dt>Entrada</dt><dd>${fmtNum(trade?.entry_price)}</dd>
          <dt>Stop / TP</dt><dd>${fmtNum(trade?.stop_loss)} / ${fmtNum(trade?.take_profit)}</dd>
          <dt>Saída</dt><dd>${fmtNum(trade?.exit_price)}</dd>
          <dt>PnL</dt><dd>${fmtNum(trade?.pnl_usdt)} USDT (${fmtNum(trade?.pnl_pct)}%)</dd>
          <dt>Motivo fechamento</dt><dd>${trade?.close_reason || "—"}</dd>
          <dt>Contexto abertura</dt><dd>Score ${trade?.context_score ?? ctx?.context_score ?? "—"} · ${trade?.context_verdict ?? ctx?.context_verdict ?? "—"}</dd>
          <dt>Alerta origem</dt><dd>${trade?.alert_id ? "#" + trade.alert_id : "—"}</dd>
          <dt>Aberto / Fechado</dt><dd>${fmtDate(trade?.opened_at)} / ${fmtDate(trade?.closed_at)}</dd>
        </dl>
        <div class="modal-actions">
          <button type="button" class="secondary" id="modal-close">Fechar</button>
        </div>
      </div>
    </div>`;
  document.getElementById("modal-close").onclick = closeModal;
  document.getElementById("modal-backdrop").onclick = (e) => {
    if (e.target.id === "modal-backdrop") closeModal();
  };
}

async function triggerScan() {
  if (!confirm("Disparar scan DIVAP agora? Pode gerar alertas no Telegram.")) return;
  const btn = document.getElementById("scan-btn");
  btn.disabled = true;
  try {
    const res = await fetch("/dashboard/scan", { method: "POST", credentials: "same-origin" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Falha no scan");
    const d = body.data || {};
    showSuccess(`Scan concluído — ${d.signals ?? 0} sinais, ${d.errors ?? 0} erros`);
    await loadDashboard();
  } catch (err) {
    showError(err.message || "Falha ao disparar scan");
  } finally {
    btn.disabled = false;
  }
}

function bindTableClicks() {
  document.getElementById("alerts-body")?.addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-alert-id]");
    if (row) openAlertModal(row.dataset.alertId);
  });
  document.getElementById("open-trades-body")?.addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-trade-id]");
    if (row) openTradeModal(row.dataset.tradeId);
  });
  document.getElementById("trades-body")?.addEventListener("click", (e) => {
    const row = e.target.closest("tr[data-trade-id]");
    if (row) openTradeModal(row.dataset.tradeId);
  });
}

async function loadDashboard() {
  hideError();
  try {
    const payload = await fetchDashboard();
    const d = payload.data || {};
    lastData = d;
    renderBadges(d.health, d.stats, d.scan);
    renderScan(d.scan);
    renderOpenTrades(d.open_trades);
    renderTrades(d.trades);
    renderAlerts(d.alerts);
    renderPnlChart(d.pnl_series);
    loadSlowExtras(d.stats);
    loadStrategyExtras();
    loadTradingReadiness();
    document.getElementById("footer-updated").textContent =
      "Atualizado: " + new Date().toLocaleString("pt-BR");
    document.getElementById("refresh-label").textContent = "Próximo refresh em 30s";
  } catch (err) {
    showError(err.message || "Falha ao carregar dados");
    if (String(err.message).toLowerCase().includes("sessão") || String(err.message).includes("401")) {
      setTimeout(showLogin, 1200);
    }
  }
}

function showApp() {
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  loadDashboard();
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(loadDashboard, REFRESH_MS);
}

function showLogin() {
  appView.classList.add("hidden");
  loginView.classList.remove("hidden");
  if (refreshTimer) clearInterval(refreshTimer);
}

function registerPwa() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/dashboard/static/sw.js?v=2", { scope: "/dashboard/" })
    .then((reg) => {
      reg.addEventListener("updatefound", () => {
        const worker = reg.installing;
        worker?.addEventListener("statechange", () => {
          if (worker.state === "installed" && navigator.serviceWorker.controller) {
            worker.postMessage({ type: "SKIP_WAITING" });
          }
        });
      });
      if (reg.waiting) reg.waiting.postMessage({ type: "SKIP_WAITING" });
    })
    .catch(() => {});
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!sessionStorage.getItem("divap-sw-reloaded")) {
      sessionStorage.setItem("divap-sw-reloaded", "1");
      window.location.reload();
    }
  });
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hideLoginError();
  const key = document.getElementById("api-key-input").value.trim();
  if (!key) return;
  try {
    await login(key);
    document.getElementById("api-key-input").value = "";
    showApp();
  } catch (err) {
    showLoginError(err.message || "Chave inválida");
  }
});

document.getElementById("refresh-btn").addEventListener("click", loadDashboard);
document.getElementById("logout-btn").addEventListener("click", async () => {
  await logoutSession();
  showLogin();
});
document.getElementById("scan-btn")?.addEventListener("click", triggerScan);
document.getElementById("filter-symbol")?.addEventListener("change", loadDashboard);
document.getElementById("filter-tf")?.addEventListener("change", loadDashboard);
document.getElementById("filter-conf")?.addEventListener("change", loadDashboard);
document.getElementById("filter-24h")?.addEventListener("change", loadDashboard);
document.getElementById("save-bankroll-btn")?.addEventListener("click", async () => {
  try {
    const data = await saveBankroll(
      document.getElementById("active-profile-select")?.value,
      document.getElementById("monthly-target-input")?.value,
    );
    renderBankroll(data.bankroll, data.profiles);
    showSuccess("Gestão da banca atualizada");
  } catch (err) {
    showError(err.message || "Falha ao salvar");
  }
});

bindTableClicks();
registerPwa();

async function bootstrap() {
  try {
    await fetchDashboard();
    showApp();
  } catch (_) {
    showLogin();
  }
}

bootstrap();
