const REFRESH_MS = 30000;

let refreshTimer = null;
let lastData = null;
let lastHighAlertId = Number(localStorage.getItem("divap-last-alert-id") || 0);

const GATE_LABELS = {
  trading_disabled: "Trading desligado",
  testnet_required: "Testnet não configurado",
  live_mode_requires_production_keys: "Modo live exige chaves produção",
  confidence_below_threshold: "Confiança abaixo do mínimo",
  timeframe_not_allowed_for_profile: "Timeframe não permitido",
  context_reject: "Contexto reject",
  monthly_goal_protected: "Modo protegido (meta)",
  no_targets: "Sem alvos",
  max_open_trades: "Máximo de trades abertos",
  duplicate_open_trade: "Trade duplicado aberto",
  insufficient_balance: "Saldo insuficiente",
  insufficient_base_balance: "Saldo base insuficiente",
  zero_fill: "Ordem sem fill",
};

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
  const verdict = document.getElementById("filter-verdict")?.value;
  const last24 = document.getElementById("filter-24h")?.checked;
  if (symbol) params.set("symbol", symbol);
  if (tf) params.set("timeframe", tf);
  if (conf) params.set("confidence", conf);
  if (verdict) params.set("verdict", verdict);
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

async function fetchDashboardSettings() {
  const res = await fetch("/dashboard/settings", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Erro ${res.status}`);
  return body.data || {};
}

async function saveDashboardSettings(payload) {
  const res = await fetch("/dashboard/settings", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Erro ${res.status}`);
  return body.data || {};
}

function buildDashboardSettingsPayloadFromForm() {
  const binToggle = document.getElementById("binance-trading-toggle");
  const otcToggle = document.getElementById("otc-trading-toggle");
  return {
    binance_trading_enabled: binToggle ? !!binToggle.checked : undefined,
    otc_trading_enabled: otcToggle ? !!otcToggle.checked : undefined,
    trading_mode: getVal("settings-trading-mode"),
    binance_use_testnet: getChecked("settings-binance-testnet"),
    trading_min_confidence: getVal("settings-min-confidence"),
    trading_block_on_context_reject: getChecked("settings-block-reject"),
    trading_max_open_trades: Number(getVal("settings-max-open") || 50),
    trading_dry_run: getChecked("settings-dry-run"),
    context_enabled: getChecked("settings-context-enabled"),
    context_news_limit: Number(getVal("settings-news-limit") || 5),
    otc_telegram_chat_id: getVal("settings-otc-chat-id"),
  };
}

async function fetchDashboardEnvExport(payload) {
  const res = await fetch("/dashboard/settings/env-export", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Erro ${res.status}`);
  return body.data?.env_export || "";
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

function parseMoneyInput(raw) {
  if (raw == null) return null;
  let s = String(raw).trim();
  if (!s) return null;
  s = s.replace(/^(R\$|US\$|\$)\s*/i, "").replace(/[^\d.,-]/g, "");
  if (s.includes(",")) {
    s = s.replace(/\./g, "").replace(",", ".");
  }
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function formatMoneyInput(value, digits = 2) {
  if (value == null || value === "") return "";
  const n = Number(value);
  if (!Number.isFinite(n)) return "";
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function bindOtcMoneyInputs() {
  document.querySelectorAll(".otc-money-input").forEach((el) => {
    if (el.dataset.moneyBound === "1") return;
    el.dataset.moneyBound = "1";
    const digits = Number(el.dataset.decimals || 2);
    el.addEventListener("blur", () => {
      if (el.readOnly) return;
      const parsed = parseMoneyInput(el.value);
      el.value = parsed == null ? "" : formatMoneyInput(parsed, digits);
    });
  });
}

function bindOtcPctInputs() {
  document.querySelectorAll(".otc-pct-input").forEach((el) => {
    if (el.dataset.pctBound === "1") return;
    el.dataset.pctBound = "1";
    el.addEventListener("blur", () => {
      const parsed = parseMoneyInput(el.value);
      el.value = parsed == null ? "" : formatMoneyInput(parsed, 2);
    });
  });
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

function renderGoalProtected(bankroll) {
  const banner = document.getElementById("goal-protected-banner");
  const panel = document.getElementById("bankroll-panel");
  const protectedMode = bankroll?.protected_mode || bankroll?.goal_reached;
  if (banner) banner.classList.toggle("hidden", !protectedMode);
  if (panel) panel.classList.toggle("goal-reached", !!protectedMode);
}

function renderScanSummary(scan) {
  const panel = document.getElementById("scan-summary-panel");
  if (!panel) return;
  const summary = scan?.summary || {};
  const blocks = summary.gate_blocks || {};
  const blockEntries = Object.entries(blocks).sort((a, b) => b[1] - a[1]);
  const blocksHtml = blockEntries.length
    ? `<ul class="gate-blocks-list">${blockEntries.map(([k, n]) =>
        `<li><span>${gateLabel(k)}</span><span class="count">${n}×</span></li>`
      ).join("")}</ul>`
    : '<div class="empty" style="padding:0.75rem">Nenhum bloqueio registrado no último scan.</div>';
  panel.innerHTML = `
    <div class="scan-summary-stats">
      <div class="scan-stat"><div class="num">${summary.pairs_scanned ?? "—"}</div><div class="lbl">Pares analisados</div></div>
      <div class="scan-stat"><div class="num">${summary.setups_detected ?? 0}</div><div class="lbl">Setups detectados</div></div>
      <div class="scan-stat"><div class="num">${summary.signals_saved ?? scan?.last_signals ?? 0}</div><div class="lbl">Alertas novos</div></div>
      <div class="scan-stat"><div class="num">${summary.trades_executed ?? 0}</div><div class="lbl">Trades executados</div></div>
      <div class="scan-stat"><div class="num">${summary.duplicates_skipped ?? 0}</div><div class="lbl">Duplicados ignorados</div></div>
    </div>
    <h3 style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.45rem;">Bloqueios por gate</h3>
    ${blocksHtml}
  `;
}

function gateLabel(key) {
  return GATE_LABELS[key] || key.replace(/_/g, " ");
}

function checkHighAlertNotifications(alerts) {
  if (!alerts?.length || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  const high = alerts.filter((a) => a.confidence === "high");
  if (!high.length) return;
  const newestId = Math.max(...high.map((a) => a.id));
  if (newestId <= lastHighAlertId) return;
  const a = high.find((x) => x.id === newestId) || high[0];
  if (localStorage.getItem("divap-notify-enabled") === "1") {
    try {
      new Notification("DIVAP — sinal alta confiança", {
        body: `${a.symbol} ${a.timeframe} · ${a.direction === "buy" ? "Compra" : "Venda"}`,
        icon: "/dashboard/static/icon.svg",
        tag: `divap-alert-${a.id}`,
      });
    } catch (_) { /* ignore */ }
  }
  lastHighAlertId = newestId;
  localStorage.setItem("divap-last-alert-id", String(lastHighAlertId));
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

function isIosDevice() {
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

function isInstalledPwa() {
  return window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
}

function setPushBtnActive(active) {
  const btn = document.getElementById("push-btn");
  if (!btn) return;
  btn.classList.toggle("active", active);
  if (active) localStorage.setItem("divap-notify-enabled", "1");
  else localStorage.removeItem("divap-notify-enabled");
}

async function syncPushButtonState() {
  try {
    const res = await fetch("/dashboard/push/status", { credentials: "same-origin" });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) return;
    setPushBtnActive((body.data?.subscriptions || 0) > 0);
  } catch (_) { /* ignore */ }
}

async function subscribePush() {
  const btn = document.getElementById("push-btn");
  if (btn?.disabled) return;

  if (!("serviceWorker" in navigator)) {
    showError("Push não suportado neste navegador.");
    return;
  }
  if (isIosDevice() && !isInstalledPwa()) {
    showError(
      "No iPhone: adicione à Tela de Início (Safari → Compartilhar → Adicionar à Tela de Início), "
      + "abra o ícone DIVAP e toque em Push de novo."
    );
    return;
  }
  if (!("PushManager" in window)) {
    showError("Push remoto indisponível neste navegador. Use Chrome/Android ou instale o PWA no iPhone.");
    return;
  }

  if (btn) btn.disabled = true;
  hideError();

  try {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") {
      showError("Permissão negada. Ative notificações nas configurações do navegador.");
      return;
    }

    const reg = await navigator.serviceWorker.ready;
    const vapidRes = await fetch("/dashboard/push/vapid-key", { credentials: "same-origin" });
    const vapidBody = await vapidRes.json().catch(() => ({}));
    if (!vapidRes.ok) {
      showError(vapidBody.detail || "Sessão expirada — faça login e tente de novo.");
      return;
    }
    const publicKey = vapidBody.data?.public_key;
    if (!publicKey || !vapidBody.data?.configured) {
      showError("Push não configurado no servidor (VAPID).");
      return;
    }

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });

    const saveRes = await fetch("/dashboard/push/subscribe", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subscription: sub.toJSON() }),
    });
    const saveBody = await saveRes.json().catch(() => ({}));
    if (!saveRes.ok) {
      showError(saveBody.detail || "Falha ao registrar push no servidor.");
      return;
    }

    setPushBtnActive(true);
    if (saveBody.data?.test_sent) {
      showSuccess("Push ativado — verifique a notificação de teste no celular.");
    } else {
      showSuccess("Push registrado, mas o teste não chegou. Verifique permissões e tente de novo.");
    }
  } catch (err) {
    showError("Falha no push: " + (err.message || "erro desconhecido"));
    setPushBtnActive(false);
  } finally {
    if (btn) btn.disabled = false;
  }
}

function renderBadges(health, stats, scan, bankroll) {
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
  const protectedMode = bankroll?.protected_mode;
  el.innerHTML = `
    <span class="badge ${online ? "ok" : "off"}">${online ? "● Online" : "○ Offline"}</span>
    <span class="badge ${testnet ? "warn" : ""}">${testnet ? "Testnet" : stats?.trading_mode || "—"}</span>
    <span class="badge ${trading ? "ok" : "off"}" title="TRADING_ENABLED — execução automática DIVAP na Binance">Binance ${trading ? "ON" : "OFF"}</span>
    <span class="badge ${beat ? "ok beat-pulse" : "off"}" title="${beatTitle.replace(/"/g, "&quot;")}">${beat ? "● Beat ativo" : "○ Beat inativo"}</span>
    ${protectedMode ? '<span class="badge warn">🛡 Protegido</span>' : ""}
  `;
}

function renderOtcBadges(overview) {
  const el = document.getElementById("status-badges");
  if (!el) return;
  const d = overview || {};
  const online = d.connection_ok;
  const trading = d.otc_trading_enabled;
  const mode = d.account_mode ? String(d.account_mode).toLowerCase() : "—";
  el.innerHTML = `
    <span class="badge ${online ? "ok" : "off"}">${online ? "● IQ conectado" : "○ IQ offline"}</span>
    <span class="badge warn">${mode}</span>
    <span class="badge ${trading ? "ok" : "off"}" title="OTC_TRADING_ENABLED — sinais Telegram IQ Option">IQ Option ${trading ? "ON" : "OFF"}</span>
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

async function saveBankroll(activeProfileIds, monthlyTarget) {
  const payload = {};
  if (activeProfileIds?.length) payload.active_profile_ids = activeProfileIds;
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

async function loadDashboardSettings() {
  try {
    const data = await fetchDashboardSettings();
    const bin = data.binance || {};
    const otc = data.otc || {};
    const secrets = data.secrets || {};
    const binToggle = document.getElementById("binance-trading-toggle");
    const otcToggle = document.getElementById("otc-trading-toggle");
    if (binToggle) binToggle.checked = !!bin.trading_enabled;
    if (otcToggle) otcToggle.checked = !!otc.trading_enabled;
    setVal("settings-trading-mode", bin.trading_mode || "testnet");
    setChecked("settings-binance-testnet", !!bin.use_testnet);
    setVal("settings-min-confidence", bin.min_confidence || "high");
    setChecked("settings-block-reject", !!bin.block_on_reject);
    setVal("settings-max-open", String(bin.max_open_trades ?? 50));
    setChecked("settings-dry-run", !!bin.dry_run);
    setChecked("settings-context-enabled", !!bin.context_enabled);
    setVal("settings-news-limit", String(bin.context_news_limit ?? 5));
    setVal("settings-otc-chat-id", otc.telegram_chat_id || "");
    setVal("settings-iq-account-mode", otc.status?.account_mode || "—");
    const statusEl = document.getElementById("settings-secrets-status");
    if (statusEl) {
      statusEl.textContent = [
        `Binance key: ${secrets.binance_api_key_configured ? "OK" : "faltando"}`,
        `Binance secret: ${secrets.binance_api_secret_configured ? "OK" : "faltando"}`,
        `IQ MCP token: ${secrets.iqoption_mcp_token_configured ? "OK" : "faltando"}`,
        `IQ login: ${secrets.iqoption_login_configured ? "OK" : "faltando"}`,
        `Telegram bot: ${secrets.telegram_bot_token_configured ? "OK" : "faltando"}`,
      ].join(" · ");
    }
  } catch (_) {
    // silencioso — aba Configurações é opcional
  }
}

async function saveDashboardSettingsFromForm() {
  const payload = buildDashboardSettingsPayloadFromForm();
  try {
    await saveDashboardSettings(payload);
    showSuccess("Configurações atualizadas (válidas até próximo deploy).");
    if (getViewMode() === "otc") {
      loadOtc();
    } else if (getViewMode() === "binance") {
      loadDashboard();
    }
  } catch (err) {
    showError(err.message || "Falha ao salvar configurações");
  }
}

async function copyDashboardEnvBlock() {
  const btn = document.getElementById("settings-copy-env-btn");
  const payload = buildDashboardSettingsPayloadFromForm();
  try {
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Gerando…";
    }
    const text = await fetchDashboardEnvExport(payload);
    if (!text) throw new Error("Exportação vazia");
    await navigator.clipboard.writeText(text);
    showSuccess("Bloco .env copiado — cole no Easypanel (Environment).");
  } catch (err) {
    showError(err.message || "Falha ao copiar bloco .env");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Copiar bloco .env atualizado";
    }
  }
}

function setVal(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value ?? "";
}
function setChecked(id, value) {
  const el = document.getElementById(id);
  if (el) el.checked = !!value;
}
function getVal(id) {
  const el = document.getElementById(id);
  return el ? String(el.value || "").trim() : "";
}
function getChecked(id) {
  const el = document.getElementById(id);
  return !!(el && el.checked);
}

function profileFitClass(status) {
  return `fit-${status || "neutro"}`;
}

function profileLabel(id) {
  return id || "—";
}

function renderInveztBriefing(payload) {
  const card = document.getElementById("invezt-briefing-card");
  if (!card) return;
  const briefing = payload?.invezt_briefing;
  const latest = briefing?.latest;
  if (!latest) {
    card.classList.add("hidden");
    card.innerHTML = "";
    return;
  }
  card.classList.remove("hidden");
  const kindLabel = {
    crypto: "Cripto",
    forex: "Forex",
    closing: "Fechamento",
    unknown: "Geral",
  }[latest.kind] || "Briefing";
  const received = latest.received_at
    ? new Date(latest.received_at).toLocaleString("pt-BR")
    : "—";
  const crypto = latest.crypto_picks || [];
  const forex = latest.forex_picks || [];
  const biasClass = (b) => (b === "bullish" ? "bias-bullish" : b === "bearish" ? "dir-sell" : "bias-neutral");
  const cryptoHtml = crypto.length
    ? `<ul class="invezt-picks">${crypto.map((p) =>
        `<li><span class="${biasClass(p.bias)}">${p.symbol}</span> · ${p.bias || "watch"}</li>`,
      ).join("")}</ul>`
    : '<p class="invezt-empty">Sem picks cripto neste briefing.</p>';
  const forexHtml = forex.length
    ? `<ul class="invezt-picks">${forex.map((p) =>
        `<li><span class="${p.direction === "buy" ? "dir-buy" : "dir-sell"}">${p.pair}</span> · ${p.direction === "buy" ? "compra" : "venda"}</li>`,
      ).join("")}</ul>`
    : '<p class="invezt-empty">Sem pares forex neste briefing.</p>';
  const summary = latest.strategic_summary || latest.headline || "";
  card.innerHTML = `
    <div class="invezt-header">
      <div class="invezt-title">Maia / Invezt PREMIUM — ${kindLabel}</div>
      <div class="invezt-meta">Recebido: ${received}</div>
    </div>
    <div class="invezt-headline">${(latest.title || "").replace(/</g, "&lt;")}${summary ? `<br>${summary.replace(/</g, "&lt;")}` : ""}</div>
    <div class="invezt-columns">
      <div class="invezt-col"><h4>Cripto</h4>${cryptoHtml}</div>
      <div class="invezt-col"><h4>Forex</h4>${forexHtml}</div>
    </div>`;
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
  const list = document.getElementById("active-profiles-list");
  const targetInput = document.getElementById("monthly-target-input");
  const profileOptions = (profilesPayload?.profiles || []).filter((p) => p.id !== "otc");
  const activeIds = b.active_profile_ids?.length
    ? b.active_profile_ids
    : [b.active_profile_id].filter(Boolean);
  if (list && profileOptions.length) {
    list.innerHTML = profileOptions.map((p) => `
      <label class="profile-checkbox">
        <input type="checkbox" name="active-profile" value="${p.id}" ${activeIds.includes(p.id) ? "checked" : ""} />
        <span>${p.name}</span>
      </label>`).join("");
  }
  if (targetInput && b.monthly_target_usdt != null) targetInput.value = b.monthly_target_usdt;

  const progress = b.progress_pct != null ? Math.min(100, Number(b.progress_pct)) : 0;
  const reached = b.protected_mode || b.goal_reached;
  const monthlyPnl = Number(b.monthly_pnl_usdt || 0);
  const target = Number(b.monthly_target_usdt || 0);
  const summary = document.getElementById("bankroll-summary");
  renderGoalProtected(b);
  summary.innerHTML = `
    <div class="bankroll-grid">
      <div class="bankroll-stat"><div class="label">PnL mês</div><div class="value ${monthlyPnl >= 0 ? "positive" : "negative"}">${fmtNum(b.monthly_pnl_usdt)} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Meta mensal</div><div class="value">${b.monthly_target_usdt ? fmtNum(b.monthly_target_usdt) + " USDT" : "—"}</div></div>
      <div class="bankroll-stat"><div class="label">PnL semana</div><div class="value">${fmtNum(b.weekly_pnl_usdt)} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Meta semanal*</div><div class="value">${b.weekly_target_usdt ? fmtNum(b.weekly_target_usdt) : "—"} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Falta p/ meta (sem.)</div><div class="value">${b.weekly_needed_usdt ? fmtNum(b.weekly_needed_usdt) : "—"} USDT</div></div>
      <div class="bankroll-stat"><div class="label">Banca demo</div><div class="value">${b.balance_usdt ? fmtNum(b.balance_usdt) : "—"} USDT</div></div>
    </div>
    ${b.monthly_target_usdt ? `
    <div class="goal-progress-card ${reached ? "reached" : ""}">
      <div class="goal-progress-header">
        <span>Progresso da meta mensal</span>
        <strong>${progress}%</strong>
      </div>
      <div class="progress-bar"><span style="width:${progress}%"></span></div>
      <div class="subtitle" style="margin-top:0.35rem;">
        ${reached
          ? "🎯 Meta batida! Modo protegido ativo — operando só setups premium."
          : `Faltam ${fmtNum(Math.max(0, target - monthlyPnl))} USDT para a meta.`}
      </div>
    </div>` : ""}
    <p class="subtitle" style="margin-top:0.5rem;">* Meta semanal = divisão proporcional da meta mensual pelas semanas do mês.</p>
  `;

  if (profilesPayload?.profiles) renderProfiles(profilesPayload, null);
  renderInveztBriefing(profilesPayload);
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

let lastBankrollCache = null;

async function loadStrategyExtras() {
  try {
    const data = await fetchStrategy();
    if (!data) return;
    lastBankrollCache = data.bankroll;
    renderBankroll(data.bankroll, data.profiles);
    renderBadges(
      lastData?.health,
      lastData?.stats,
      lastData?.scan,
      data.bankroll,
    );
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
  const monInterval = s.monitor_interval_seconds ? Math.round(s.monitor_interval_seconds / 60) : 5;
  const monUntil = s.seconds_until_next_monitor != null ? `~${fmtDuration(s.seconds_until_next_monitor)}` : "—";
  const profile = s.active_profile_names?.length
    ? s.active_profile_names.join(", ")
    : (s.active_profile_name || "—");
  const tfs = (s.scan_timeframes || []).join(", ") || "—";
  const beat = s.beat_active ? "beat OK" : "beat —";
  document.getElementById("scan-status").textContent =
    `Perfil ${profile} · scan ${tfs} a cada ${interval} min (próx. ${until}) · monitor a cada ${monInterval} min (próx. ${monUntil}) · sinais: ${s.last_signals ?? 0} · ${beat}`;
}

function targetHitCell(hit) {
  return hit ? "✅" : "—";
}

function tradeRow(t, clickable = true) {
  const pnl = t.pnl_usdt != null ? Number(t.pnl_usdt) : null;
  const pnlHtml = pnl != null
    ? `<span class="${pnl >= 0 ? "tag-buy" : "tag-sell"}">${fmtNum(pnl)}</span>`
    : "—";
  const hits = t.target_hits || [false, false, false];
  const current = t.status === "open" ? fmtNum(t.current_price) : "—";
  const exitPx = fmtNum(t.exit_display || t.exit_price);
  return `<tr class="${clickable ? "clickable" : ""}" data-trade-id="${t.id}">
    <td>#${t.id}</td>
    <td>${t.symbol}</td>
    <td>${t.timeframe}</td>
    <td>${profileLabel(t.profile_id)}</td>
    <td>${dirLabel(t.direction)}</td>
    <td>${statusLabel(t.status)}</td>
    <td>${fmtNum(t.entry_price)}</td>
    <td>${current}</td>
    <td>${exitPx}</td>
    <td class="target-hit">${targetHitCell(hits[0])}</td>
    <td class="target-hit">${targetHitCell(hits[1])}</td>
    <td class="target-hit">${targetHitCell(hits[2])}</td>
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
    tbody.innerHTML = '<tr><td colspan="15" class="empty">Nenhum trade fechado ainda</td></tr>';
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
    renderBadges(d.health, d.stats, d.scan, lastBankrollCache);
    renderScan(d.scan);
    renderScanSummary(d.scan);
    renderOpenTrades(d.open_trades);
    renderTrades(d.trades);
    renderAlerts(d.alerts);
    checkHighAlertNotifications(d.alerts);
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

function refreshTick() {
  if (getViewMode() === "otc") {
    loadOtc();
  } else if (getViewMode() === "settings") {
    loadDashboardSettings();
  } else {
    loadDashboard();
  }
}

function showApp() {
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  applyView(getViewMode());
  syncPushButtonState();
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(refreshTick, REFRESH_MS);
  loadDashboardSettings();
}

function showLogin() {
  appView.classList.add("hidden");
  loginView.classList.remove("hidden");
  if (refreshTimer) clearInterval(refreshTimer);
}

function registerPwa() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/dashboard/static/sw.js?v=4", { scope: "/dashboard/" })
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

document.getElementById("refresh-btn").addEventListener("click", refreshTick);
document.getElementById("logout-btn").addEventListener("click", async () => {
  await logoutSession();
  showLogin();
});
document.getElementById("scan-btn")?.addEventListener("click", triggerScan);
document.getElementById("filter-symbol")?.addEventListener("change", loadDashboard);
document.getElementById("filter-tf")?.addEventListener("change", loadDashboard);
document.getElementById("filter-conf")?.addEventListener("change", loadDashboard);
document.getElementById("filter-verdict")?.addEventListener("change", () => {
  syncVerdictChips();
  loadDashboard();
});
document.getElementById("filter-24h")?.addEventListener("change", loadDashboard);
document.getElementById("push-btn")?.addEventListener("click", subscribePush);

function syncVerdictChips() {
  const val = document.getElementById("filter-verdict")?.value || "";
  document.querySelectorAll("#verdict-chips .chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.verdict === val);
  });
}

document.getElementById("verdict-chips")?.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const select = document.getElementById("filter-verdict");
  if (select) select.value = chip.dataset.verdict || "";
  syncVerdictChips();
  loadDashboard();
});

if (localStorage.getItem("divap-notify-enabled") === "1") {
  setPushBtnActive(true);
}
document.getElementById("save-bankroll-btn")?.addEventListener("click", async () => {
  try {
    const checked = [...document.querySelectorAll('input[name="active-profile"]:checked')].map(
      (el) => el.value,
    );
    const data = await saveBankroll(
      checked,
      document.getElementById("monthly-target-input")?.value,
    );
    renderBankroll(data.bankroll, data.profiles);
    showSuccess("Gestão da banca atualizada");
  } catch (err) {
    showError(err.message || "Falha ao salvar");
  }
});

document.getElementById("settings-save-btn")?.addEventListener("click", saveDashboardSettingsFromForm);
document.getElementById("settings-copy-env-btn")?.addEventListener("click", copyDashboardEnvBlock);

/* ===================== IQ Option (OTC) ===================== */
let otcOverview = null;
let otcPnlLoaded = false;
let otcFxAutoTimer = null;
let otcChartLayout = null;
let otcChartSeries = [];
let otcTradesDateFilter = null;

const OTC_PERIOD_LABELS = {
  day: "Dia",
  week: "Semana",
  month: "Mês",
  quarter: "Trimestre",
  semester: "Semestre",
  year: "Ano",
};
const DEFAULT_USD_BRL = 5.4;
const OTC_FX_REFRESH_MS = 10 * 60 * 1000;

function getViewMode() {
  const mode = localStorage.getItem("divap_view");
  if (mode === "otc" || mode === "settings") return mode;
  return "binance";
}
function getOtcCurrency() {
  return localStorage.getItem("otc_currency") === "brl" ? "brl" : "usd";
}
function getOtcPeriod() {
  return localStorage.getItem("otc_period") || "day";
}
function otcRate() {
  const fromOverview = Number(otcOverview?.usd_brl_rate);
  if (Number.isFinite(fromOverview) && fromOverview > 0) return fromOverview;
  const fromInput = parseMoneyInput(document.getElementById("otc-usd-brl")?.value);
  if (fromInput != null && fromInput > 0) return fromInput;
  return DEFAULT_USD_BRL;
}

function isOtcFxAuto() {
  return localStorage.getItem("otc_usd_brl_auto") !== "false";
}

function syncOtcFxAutoUi() {
  const auto = isOtcFxAuto();
  const input = document.getElementById("otc-usd-brl");
  const refreshBtn = document.getElementById("otc-usd-brl-refresh");
  const autoChk = document.getElementById("otc-usd-brl-auto");
  if (autoChk) autoChk.checked = auto;
  if (input) {
    input.readOnly = auto;
    input.classList.toggle("readonly", auto);
  }
  if (refreshBtn) refreshBtn.disabled = auto;
}

function updateOtcFxMeta(data) {
  const meta = document.getElementById("otc-usd-brl-meta");
  if (!meta) return;
  const when = data?.fetched_at ? fmtDate(data.fetched_at) : "agora";
  const source = data?.source || "salva";
  meta.textContent = `Fonte: ${source} · ${when}${isOtcFxAuto() ? " · automático" : ""}`;
}

async function persistOtcUsdBrlRate(rate) {
  const res = await fetch("/dashboard/otc/settings", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ usd_brl_rate: rate }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || "Falha ao salvar cotação");
  if (body.data) otcOverview = body.data;
}

async function fetchOtcUsdBrlRate({ persist = false, silent = false } = {}) {
  const res = await fetch("/dashboard/otc/usd-brl", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || body.error || `Erro ${res.status}`);
  const data = body.data || {};
  const rate = parseMoneyInput(data.rate);
  if (rate == null || rate <= 0) throw new Error("Cotação inválida");

  if (otcOverview) otcOverview.usd_brl_rate = rate;
  const input = document.getElementById("otc-usd-brl");
  if (input && document.activeElement !== input) {
    input.value = formatMoneyInput(rate, 4);
  }
  updateOtcFxMeta(data);

  if (persist) {
    await persistOtcUsdBrlRate(rate);
  }

  if (otcOverview && getOtcCurrency() === "brl") {
    renderOtcBalance(otcOverview);
    renderOtcGoals(otcOverview);
    renderOtcStats(otcOverview);
    renderOtcMartingale(otcOverview);
    renderOtcPeriodTotals(otcOverview);
    loadOtcTradesFiltered();
    loadOtcPnl();
  }
  return rate;
}

function stopOtcFxAutoRefresh() {
  if (otcFxAutoTimer) clearInterval(otcFxAutoTimer);
  otcFxAutoTimer = null;
}

function startOtcFxAutoRefresh() {
  stopOtcFxAutoRefresh();
  if (!isOtcFxAuto()) return;
  otcFxAutoTimer = setInterval(() => {
    if (getViewMode() === "otc") {
      fetchOtcUsdBrlRate({ persist: true, silent: true }).catch(() => {});
    }
  }, OTC_FX_REFRESH_MS);
}

function otcMoney(usd, { sign = false } = {}) {
  if (usd == null || usd === "") return "—";
  let n = Number(usd);
  if (Number.isNaN(n)) return "—";
  let symbol = "$";
  if (getOtcCurrency() === "brl") {
    n = n * otcRate();
    symbol = "R$";
  }
  const prefix = sign && n > 0 ? "+" : "";
  return `${prefix}${symbol} ${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function signClass(val) {
  const n = Number(val);
  if (Number.isNaN(n) || n === 0) return "";
  return n > 0 ? "positive" : "negative";
}

function card(label, value, { cls = "", sub = "", highlight = false } = {}) {
  return `<div class="card${highlight ? " highlight" : ""}">
    <div class="card-label">${label}</div>
    <div class="card-value ${cls}">${value}</div>
    ${sub ? `<div class="card-sub">${sub}</div>` : ""}
  </div>`;
}

function applyView(mode) {
  const view = mode === "otc" || mode === "settings" ? mode : "binance";
  localStorage.setItem("divap_view", view);
  document.body.setAttribute("data-view", view);
  document.querySelectorAll(".view-switch-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  const subtitle = document.getElementById("header-subtitle");
  if (subtitle) {
    if (view === "otc") {
      subtitle.textContent = "IQ Option · binárias OTC via Telegram";
    } else if (view === "settings") {
      subtitle.textContent = "Configurações gerais · Binance e IQ Option";
    } else {
      subtitle.textContent = "Demo Binance testnet · scan automático 15 min";
    }
  }
  if (view === "otc") {
    loadOtc();
  } else if (view === "settings") {
    loadDashboardSettings();
  } else {
    loadDashboard();
  }
}

async function fetchOtcOverview() {
  const res = await fetch("/dashboard/otc/overview", { credentials: "same-origin" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || body.error || `Erro ${res.status}`);
  return body.data || {};
}

async function fetchOtcPnl(period) {
  const res = await fetch(`/dashboard/otc/pnl?period=${encodeURIComponent(period)}`, {
    credentials: "same-origin",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || body.error || `Erro ${res.status}`);
  return body.data || {};
}

async function fetchOtcTradesByDay(dateKey) {
  const res = await fetch(`/dashboard/otc/trades?date=${encodeURIComponent(dateKey)}`, {
    credentials: "same-origin",
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || body.error || `Erro ${res.status}`);
  return body.data || {};
}

async function loadOtc() {
  try {
    otcOverview = await fetchOtcOverview();
    renderOtc(otcOverview);
    syncOtcFxAutoUi();
    bindOtcMoneyInputs();
    bindOtcPctInputs();
    if (isOtcFxAuto()) {
      try {
        await fetchOtcUsdBrlRate({ persist: true, silent: true });
      } catch (_) {
        updateOtcFxMeta({ source: "salva", fetched_at: null });
      }
      startOtcFxAutoRefresh();
    } else {
      stopOtcFxAutoRefresh();
      updateOtcFxMeta({ source: "manual", fetched_at: null });
    }
    await loadOtcPnl();
    document.getElementById("footer-updated").textContent =
      "Atualizado: " + new Date().toLocaleString("pt-BR");
  } catch (err) {
    showError(err.message || "Falha ao carregar IQ Option");
    if (String(err.message).includes("401")) setTimeout(showLogin, 1200);
  }
}

function renderOtc(d) {
  renderOtcBadges(d);
  renderOtcStatusLine(d);
  renderOtcStopBanner(d);
  renderOtcBalance(d);
  renderOtcGoals(d);
  renderOtcStats(d);
  renderOtcMartingale(d);
  renderOtcPeriodTotals(d);
  loadOtcTradesFiltered();
  fillOtcSettingsForm(d.settings);
}

function renderOtcStatusLine(d) {
  const el = document.getElementById("otc-status-line");
  if (!el) return;
  const conn = d.connection_ok ? "🟢 conectado" : "🔴 sem conexão";
  const mode = d.account_mode ? d.account_mode.toLowerCase() : "—";
  const trading = d.otc_trading_enabled ? "trading ON" : "trading OFF";
  el.textContent = `${conn} · conta ${mode} · ${trading} · stake ${otcMoney(d.settings?.stake_usd || d.default_stake_usd)}`;
}

function renderOtcStopBanner(d) {
  const el = document.getElementById("otc-stop-banner");
  if (!el) return;
  const reason = d.stop?.active_reason;
  if (!reason) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden");
  if (reason === "stop_win") {
    el.className = "otc-stop-banner win";
    el.textContent = "🎯 Stop win atingido — operações pausadas até amanhã. Limite de lucro do dia atingido!";
  } else {
    el.className = "otc-stop-banner loss";
    el.textContent = "🛑 Stop loss diário atingido — operações pausadas para preservar a banca.";
  }
}

function renderOtcBalance(d) {
  const b = d.bankroll || {};
  const cards = [
    card("Saldo atual", otcMoney(b.balance_usd), { highlight: true }),
    card("Banca inicial", otcMoney(b.initial_bankroll_usd), {
      sub: b.initial_bankroll_usd ? "" : "defina abaixo",
    }),
    card("Lucro / Prejuízo", otcMoney(b.profit_abs_usd, { sign: true }), {
      cls: signClass(b.profit_abs_usd),
      sub: b.profit_pct != null ? `${b.profit_pct > 0 ? "+" : ""}${fmtNum(b.profit_pct)}% da banca` : "",
    }),
    card("PnL acumulado", otcMoney(b.accumulated_pnl_usd, { sign: true }), {
      cls: signClass(b.accumulated_pnl_usd),
      sub: "todas as operações",
    }),
  ];
  document.getElementById("otc-balance-grid").innerHTML = cards.join("");
}

function goalCard(title, goal) {
  if (!goal) {
    return `<div class="otc-goal-card">
      <div class="otc-goal-top"><span class="otc-goal-title">${title}</span></div>
      <div class="otc-goal-sub">Defina a meta na gestão de banca abaixo.</div>
    </div>`;
  }
  const pct = Math.max(0, Math.min(100, Number(goal.progress_pct) || 0));
  return `<div class="otc-goal-card">
    <div class="otc-goal-top">
      <span class="otc-goal-title">${title}</span>
      <span class="otc-goal-value ${signClass(goal.achieved_usd)}">${otcMoney(goal.achieved_usd, { sign: true })}</span>
    </div>
    <div class="otc-progress"><div class="otc-progress-bar ${goal.reached ? "reached" : ""}" style="width:${pct}%"></div></div>
    <div class="otc-goal-sub">${fmtNum(goal.progress_pct)}% de ${otcMoney(goal.goal_usd)} ${goal.reached ? "· ✅ atingida" : ""}</div>
  </div>`;
}

function renderOtcGoals(d) {
  const g = d.goals || {};
  document.getElementById("otc-goals").innerHTML =
    goalCard("Meta diária", g.daily) + goalCard("Meta mensal", g.monthly);
}

function renderOtcStats(d) {
  const s = d.stats || {};
  const cards = [
    card("Operações", s.operations ?? 0),
    card("Vitórias", s.wins ?? 0, { cls: "positive" }),
    card("Derrotas", s.losses ?? 0, { cls: "negative" }),
    card("Taxa de acerto", `${fmtNum(s.win_rate_pct ?? 0)}%`),
  ];
  document.getElementById("otc-stats-grid").innerHTML = cards.join("");
}

function renderOtcMartingale(d) {
  const s = d.stats || {};
  const cards = [
    card("Win sem gale", s.win_no_gale ?? 0, { cls: "positive", sub: "venceu na entrada" }),
    card("Foram p/ gale", s.went_to_gale ?? 0, { sub: "precisaram proteger" }),
    card("1ª proteção", `${s.protection1_wins ?? 0}/${s.protection1_count ?? 0}`, {
      sub: "wins / acionadas",
    }),
    card("2ª proteção", `${s.protection2_wins ?? 0}/${s.protection2_count ?? 0}`, {
      sub: "wins / acionadas",
    }),
  ];
  document.getElementById("otc-martingale-grid").innerHTML = cards.join("");
}

function renderOtcPeriodTotals(d) {
  const totals = d.period_totals || {};
  const labels = d.period_labels || {};
  const order = ["day", "week", "month", "quarter", "semester", "year"];
  const cards = order
    .filter((p) => totals[p])
    .map((p) =>
      card(labels[p] || p, otcMoney(totals[p].pnl_usd, { sign: true }), {
        cls: signClass(totals[p].pnl_usd),
        sub: `${totals[p].operations} op.`,
      }),
    );
  document.getElementById("otc-period-totals").innerHTML = cards.join("");
}

function formatOtcBucketLabel(period, bucketIso) {
  if (!bucketIso) return "—";
  const d = new Date(bucketIso);
  if (Number.isNaN(d.getTime())) return bucketIso;
  const tzOpts = { timeZone: "America/Sao_Paulo" };
  if (period === "day") {
    return d.toLocaleDateString("pt-BR", { ...tzOpts, day: "2-digit", month: "2-digit", year: "numeric" });
  }
  if (period === "week") {
    return `Sem. ${d.toLocaleDateString("pt-BR", { ...tzOpts, day: "2-digit", month: "short", year: "numeric" })}`;
  }
  if (period === "month") {
    return d.toLocaleDateString("pt-BR", { ...tzOpts, month: "long", year: "numeric" });
  }
  if (period === "quarter") {
    const month = Number(
      new Intl.DateTimeFormat("pt-BR", { ...tzOpts, month: "numeric" }).format(d),
    );
    const year = new Intl.DateTimeFormat("pt-BR", { ...tzOpts, year: "numeric" }).format(d);
    return `T${Math.ceil(month / 3)}/${year}`;
  }
  if (period === "semester") {
    const month = Number(
      new Intl.DateTimeFormat("pt-BR", { ...tzOpts, month: "numeric" }).format(d),
    );
    const year = new Intl.DateTimeFormat("pt-BR", { ...tzOpts, year: "numeric" }).format(d);
    return month <= 6 ? `S1/${year}` : `S2/${year}`;
  }
  if (period === "year") {
    return new Intl.DateTimeFormat("pt-BR", { ...tzOpts, year: "numeric" }).format(d);
  }
  return d.toLocaleDateString("pt-BR", tzOpts);
}

function bucketToLocalDateKey(bucketIso) {
  if (!bucketIso) return null;
  const d = new Date(bucketIso);
  if (Number.isNaN(d.getTime())) return null;
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(d);
}

function updateOtcTradesHint(text) {
  const el = document.getElementById("otc-trades-hint");
  if (el) el.textContent = text;
}

async function loadOtcTradesFiltered() {
  const dateInput = document.getElementById("otc-trades-date");
  if (dateInput && otcTradesDateFilter) dateInput.value = otcTradesDateFilter;

  if (otcTradesDateFilter) {
    try {
      const data = await fetchOtcTradesByDay(otcTradesDateFilter);
      renderOtcTrades(data.trades || []);
      const dayLabel = new Date(otcTradesDateFilter + "T12:00:00").toLocaleDateString("pt-BR");
      updateOtcTradesHint(
        `${data.count ?? 0} operações em ${dayLabel} · Total: ${otcMoney(data.total_pnl_usd, { sign: true })}`,
      );
    } catch (err) {
      showError(err.message || "Falha ao carregar operações do dia");
    }
    return;
  }

  if (otcOverview?.trades) {
    renderOtcTrades(otcOverview.trades);
    updateOtcTradesHint("Últimas 50 operações. Clique em uma barra do gráfico ou escolha um dia.");
  }
}

function setOtcTradesDateFilter(dateKey) {
  otcTradesDateFilter = dateKey || null;
  const dateInput = document.getElementById("otc-trades-date");
  if (dateInput) dateInput.value = otcTradesDateFilter || "";
  loadOtcTradesFiltered();
}

function renderOtcTrades(trades) {
  const body = document.getElementById("otc-trades-body");
  if (!body) return;
  if (!trades?.length) {
    body.innerHTML = `<tr><td colspan="9" class="empty">Nenhuma operação registrada ainda.</td></tr>`;
    return;
  }
  body.innerHTML = trades
    .map((t) => {
      const when = fmtDate(t.closed_at || t.opened_at);
      const resultTag =
        t.result === "win"
          ? '<span class="tag-buy">WIN</span>'
          : t.result === "loss"
          ? '<span class="tag-sell">LOSS</span>'
          : statusLabel(t.status);
      return `<tr>
        <td>${t.id ?? "—"}</td>
        <td>${t.asset ?? "—"}</td>
        <td>${dirLabel(t.direction)}</td>
        <td>${t.level_label}</td>
        <td>${otcMoney(t.stake_usd)}</td>
        <td>${resultTag}</td>
        <td class="${signClass(t.pnl_usd)}">${otcMoney(t.pnl_usd, { sign: true })}</td>
        <td>${t.order_id ?? "—"}</td>
        <td>${when}</td>
      </tr>`;
    })
    .join("");
}

function fillOtcSettingsForm(s) {
  if (!s) return;
  const setMoney = (id, v, digits = 2) => {
    const el = document.getElementById(id);
    if (el && document.activeElement !== el) {
      el.value = v != null && v !== "" ? formatMoneyInput(v, digits) : "";
    }
  };
  const setPct = (id, v) => {
    const el = document.getElementById(id);
    if (el && document.activeElement !== el) {
      el.value = v != null && v !== "" ? formatMoneyInput(v, 2) : "";
    }
  };
  const setChk = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.checked = !!v;
  };
  setMoney("otc-stake", s.stake_usd);
  setMoney("otc-bankroll", s.initial_bankroll_usd);
  setMoney("otc-daily-goal", s.daily_goal_usd);
  setMoney("otc-monthly-goal", s.monthly_goal_usd);
  setPct("otc-stop-win-pct", s.daily_stop_win_pct);
  setPct("otc-stop-loss-pct", s.daily_stop_loss_pct);
  if (!isOtcFxAuto() || document.activeElement?.id !== "otc-usd-brl") {
    setMoney("otc-usd-brl", s.usd_brl_rate, 4);
  }
  setChk("otc-stop-win-enabled", s.stop_win_enabled);
  setChk("otc-stop-loss-enabled", s.stop_loss_enabled);
}

async function loadOtcPnl() {
  const period = getOtcPeriod();
  try {
    const data = await fetchOtcPnl(period);
    if (!otcPnlLoaded) {
      const select = document.getElementById("otc-period-select");
      if (select && data.available_periods) {
        select.innerHTML = data.available_periods
          .map((p) => `<option value="${p.id}">${p.label}</option>`)
          .join("");
        select.value = period;
      }
      otcPnlLoaded = true;
    }
    renderOtcPnl(data);
  } catch (err) {
    showError(err.message || "Falha ao carregar PnL");
  }
}

function renderOtcPnl(data) {
  const totalEl = document.getElementById("otc-pnl-total");
  if (totalEl) {
    totalEl.innerHTML = `Total no período exibido: <strong class="${signClass(data.total_usd)}">${otcMoney(data.total_usd, { sign: true })}</strong>`;
  }
  otcChartSeries = data.series || [];
  drawOtcChart(document.getElementById("otc-pnl-chart"), otcChartSeries, null, data.period || getOtcPeriod());
  bindOtcChartInteraction();
}

function otcBarIndexFromX(x) {
  if (!otcChartLayout) return null;
  const idx = Math.floor(x / otcChartLayout.slot);
  if (idx < 0 || idx >= otcChartLayout.series.length) return null;
  return idx;
}

function hideOtcChartTooltip() {
  const tooltip = document.getElementById("otc-pnl-tooltip");
  if (tooltip) tooltip.classList.add("hidden");
}

function showOtcChartTooltip(clientX, clientY, index) {
  const tooltip = document.getElementById("otc-pnl-tooltip");
  const wrap = document.querySelector(".otc-chart-wrap");
  if (!tooltip || !wrap || !otcChartSeries[index]) return;

  const point = otcChartSeries[index];
  const period = otcChartLayout?.chartPeriod || getOtcPeriod();
  const title = formatOtcBucketLabel(period, point.bucket);
  const breakdown = point.breakdown || {};
  const order = ["day", "week", "month", "quarter", "semester", "year"];
  const rows = order
    .map((p) => {
      const b = breakdown[p] || {};
      const pnl = b.pnl_usd ?? "0";
      return `<div class="otc-tip-row"><span>${OTC_PERIOD_LABELS[p]}</span><span class="${signClass(pnl)}">${otcMoney(pnl, { sign: true })} <small>(${b.operations ?? 0} op.)</small></span></div>`;
    })
    .join("");

  tooltip.innerHTML = `
    <div class="otc-tip-title">${title}</div>
    <div class="otc-tip-bar">Esta barra: <strong class="${signClass(point.pnl_usd)}">${otcMoney(point.pnl_usd, { sign: true })}</strong> · ${point.operations ?? 0} op.</div>
    ${rows}
    <div class="otc-tip-hint">Clique para filtrar operações do dia</div>`;
  tooltip.classList.remove("hidden");

  const rect = wrap.getBoundingClientRect();
  let left = clientX - rect.left + 12;
  let top = clientY - rect.top - 8;
  const maxLeft = rect.width - tooltip.offsetWidth - 8;
  if (left > maxLeft) left = Math.max(8, maxLeft);
  if (top + tooltip.offsetHeight > rect.height) top = rect.height - tooltip.offsetHeight - 8;
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function bindOtcChartInteraction() {
  const canvas = document.getElementById("otc-pnl-chart");
  if (!canvas || canvas.dataset.otcBound === "1") return;
  canvas.dataset.otcBound = "1";

  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const idx = otcBarIndexFromX(x);
    if (idx == null) {
      hideOtcChartTooltip();
      drawOtcChart(canvas, otcChartSeries, null, otcChartLayout?.chartPeriod || getOtcPeriod());
      return;
    }
    showOtcChartTooltip(e.clientX, e.clientY, idx);
    drawOtcChart(canvas, otcChartSeries, idx, otcChartLayout?.chartPeriod || getOtcPeriod());
  });

  canvas.addEventListener("mouseleave", () => {
    hideOtcChartTooltip();
    drawOtcChart(canvas, otcChartSeries, null, otcChartLayout?.chartPeriod || getOtcPeriod());
  });

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const idx = otcBarIndexFromX(e.clientX - rect.left);
    if (idx == null) return;
    const dayKey = bucketToLocalDateKey(otcChartSeries[idx]?.bucket);
    if (dayKey) setOtcTradesDateFilter(dayKey);
  });
}

function drawOtcChart(canvas, series, highlightIndex = null, chartPeriod = "day") {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.parentElement.getBoundingClientRect();
  const w = rect.width || 600;
  const h = 180;
  canvas.width = w * dpr;
  canvas.height = h * dpr;
  canvas.style.width = w + "px";
  canvas.style.height = h + "px";
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);

  if (!series.length) {
    ctx.fillStyle = "#a3a3a3";
    ctx.font = "13px Segoe UI, sans-serif";
    ctx.fillText("Sem dados no período.", 12, h / 2);
    otcChartLayout = null;
    return;
  }

  const values = series.map((p) => Number(p.pnl_usd) * (getOtcCurrency() === "brl" ? otcRate() : 1));
  const max = Math.max(0, ...values);
  const min = Math.min(0, ...values);
  const range = max - min || 1;
  const pad = 24;
  const usableH = h - pad * 2;
  const zeroY = pad + (max / range) * usableH;
  const n = series.length;
  const slot = w / n;
  const barW = Math.max(4, Math.min(40, slot * 0.6));

  otcChartLayout = { series, slot, barW, w, h, chartPeriod };

  ctx.strokeStyle = "#333";
  ctx.beginPath();
  ctx.moveTo(0, zeroY);
  ctx.lineTo(w, zeroY);
  ctx.stroke();

  series.forEach((p, i) => {
    const v = values[i];
    const x = slot * i + (slot - barW) / 2;
    const barH = (Math.abs(v) / range) * usableH;
    const y = v >= 0 ? zeroY - barH : zeroY;
    if (i === highlightIndex) {
      ctx.fillStyle = v >= 0 ? "#4ade80" : "#f87171";
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 1.5;
      ctx.fillRect(x, y, barW, barH || 1);
      ctx.strokeRect(x, y, barW, barH || 1);
      ctx.lineWidth = 1;
    } else {
      ctx.fillStyle = v >= 0 ? "#22c55e" : "#ef4444";
      ctx.fillRect(x, y, barW, barH || 1);
    }
  });
}

document.querySelectorAll(".view-switch-btn").forEach((btn) => {
  btn.addEventListener("click", () => applyView(btn.dataset.view));
});

document.querySelectorAll(".currency-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    localStorage.setItem("otc_currency", btn.dataset.currency);
    document.querySelectorAll(".currency-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.currency === btn.dataset.currency);
    });
    if (otcOverview) {
      renderOtc(otcOverview);
      loadOtcPnl();
    }
  });
});

document.getElementById("otc-period-select")?.addEventListener("change", (e) => {
  localStorage.setItem("otc_period", e.target.value);
  loadOtcPnl();
});

document.getElementById("otc-trades-date")?.addEventListener("change", (e) => {
  setOtcTradesDateFilter(e.target.value || null);
});

document.getElementById("otc-trades-date-clear")?.addEventListener("click", () => {
  setOtcTradesDateFilter(null);
});

document.getElementById("otc-settings-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const numOrNull = (id) => parseMoneyInput(document.getElementById(id)?.value);
  const payload = {
    stake_usd: numOrNull("otc-stake"),
    initial_bankroll_usd: numOrNull("otc-bankroll"),
    daily_goal_usd: numOrNull("otc-daily-goal"),
    monthly_goal_usd: numOrNull("otc-monthly-goal"),
    daily_stop_win_pct: numOrNull("otc-stop-win-pct"),
    daily_stop_loss_pct: numOrNull("otc-stop-loss-pct"),
    usd_brl_rate: numOrNull("otc-usd-brl"),
    stop_win_enabled: document.getElementById("otc-stop-win-enabled")?.checked || false,
    stop_loss_enabled: document.getElementById("otc-stop-loss-enabled")?.checked || false,
  };
  const btn = document.getElementById("otc-save-btn");
  btn.disabled = true;
  try {
    const res = await fetch("/dashboard/otc/settings", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || "Falha ao salvar");
    otcOverview = body.data || otcOverview;
    renderOtc(otcOverview);
    showSuccess("Configuração do IQ Option salva");
  } catch (err) {
    showError(err.message || "Falha ao salvar configuração");
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("otc-usd-brl-refresh")?.addEventListener("click", async () => {
  const btn = document.getElementById("otc-usd-brl-refresh");
  try {
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Atualizando…";
    }
    await fetchOtcUsdBrlRate({ persist: true });
    showSuccess("Cotação USD/BRL atualizada");
  } catch (err) {
    showError(err.message || "Falha ao atualizar cotação");
  } finally {
    if (btn) {
      btn.disabled = isOtcFxAuto();
      btn.textContent = "Atualizar";
    }
  }
});

document.getElementById("otc-usd-brl-auto")?.addEventListener("change", async (e) => {
  const auto = !!e.target.checked;
  localStorage.setItem("otc_usd_brl_auto", auto ? "true" : "false");
  syncOtcFxAutoUi();
  if (auto) {
    try {
      await fetchOtcUsdBrlRate({ persist: true, silent: true });
    } catch (_) {
      updateOtcFxMeta({ source: "salva", fetched_at: null });
    }
    startOtcFxAutoRefresh();
  } else {
    stopOtcFxAutoRefresh();
    updateOtcFxMeta({ source: "manual", fetched_at: null });
  }
});

// Sincroniza botão de moeda com a preferência salva
document.querySelectorAll(".currency-btn").forEach((b) => {
  b.classList.toggle("active", b.dataset.currency === getOtcCurrency());
});

bindTableClicks();
registerPwa();
bindOtcMoneyInputs();
bindOtcPctInputs();
syncOtcFxAutoUi();

async function bootstrap() {
  try {
    await fetchDashboard();
    showApp();
  } catch (_) {
    showLogin();
  }
}

bootstrap();
