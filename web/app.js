const I18N = {
  zh: {
    eyebrow: "Pearl plain miner 控制台",
    subhead: "PlainProof-only 的 Pearl 挖矿启动器。",
    admireBackground: "欣赏背景",
    refresh: "刷新",
    scopeTitle: "范围故意收窄。",
    scopeText: "PapiMiner 只启动 plain miner 并记录本地运行证据。AI 实验放在 Papipearls。",
    runTitle: "运行控制",
    runDesc: "选择 plain miner 档案、GPU、worker 和 PRL 收款地址，然后启动或停止。",
    profile: "运行档案",
    gpuLabel: "GPU(s)",
    wallet: "PRL 地址",
    show: "显示",
    hide: "隐藏",
    poolHost: "矿池 host",
    poolPort: "矿池 port",
    poolTls: "TLS",
    openMonitor: "启动时打开监控窗口",
    start: "启动",
    stop: "停止",
    importTitle: "导入 plain miner 档案",
    importDesc: "只接受 kind=plain 的启动档案。钱包地址、worker、本地路径都写入 local/。",
    plainTemplate: "填入模板",
    importProfile: "导入档案",
    runtimeTitle: "运行进程",
    loading: "读取中...",
    appearance: "外观",
    chooseBackground: "选择背景图",
    resetBackground: "重置背景",
    noProfiles: "没有可用 plain 档案",
    noRuntime: "暂无运行进程",
    noGpu: "没有 GPU 数据",
    started: "已启动",
    stopped: "已停止",
    imported: "已导入",
    importFailed: "导入失败",
    startFailed: "启动失败",
    stopFailed: "停止失败",
    backgroundSaved: "背景已保存",
    backgroundReset: "背景已重置",
  },
  en: {
    eyebrow: "Pearl plain miner console",
    subhead: "PlainProof-only launcher for Pearl mining.",
    admireBackground: "Admire background",
    refresh: "Refresh",
    scopeTitle: "Scope is intentionally narrow.",
    scopeText: "PapiMiner starts plain miners and records local runtime evidence. AI experiments belong in Papipearls.",
    runTitle: "Run Control",
    runDesc: "Choose a plain miner profile, GPU, worker, and PRL receive address, then start or stop it.",
    profile: "Run profile",
    gpuLabel: "GPU(s)",
    wallet: "PRL address",
    show: "Show",
    hide: "Hide",
    poolHost: "Pool host",
    poolPort: "Pool port",
    poolTls: "TLS",
    openMonitor: "Open monitor window on start",
    start: "Start",
    stop: "Stop",
    importTitle: "Import plain miner profile",
    importDesc: "Only kind=plain run profiles are accepted. Wallet, worker, and local paths stay in local/.",
    plainTemplate: "Insert template",
    importProfile: "Import profile",
    runtimeTitle: "Runtime",
    loading: "Loading...",
    appearance: "Appearance",
    chooseBackground: "Choose background",
    resetBackground: "Reset background",
    noProfiles: "No plain profiles available",
    noRuntime: "No runtime process",
    noGpu: "No GPU data",
    started: "Started",
    stopped: "Stopped",
    imported: "Imported",
    importFailed: "Import failed",
    startFailed: "Start failed",
    stopFailed: "Stop failed",
    backgroundSaved: "Background saved",
    backgroundReset: "Background reset",
  },
};

const state = {
  lang: localStorage.getItem("papiminer.lang") || "zh",
  profiles: [],
  runtime: [],
  status: null,
  admire: false,
};

const els = {
  backgroundStage: document.querySelector("#backgroundStage"),
  profileSelect: document.querySelector("#profileSelect"),
  runtimeGpu: document.querySelector("#runtimeGpu"),
  runtimeWorker: document.querySelector("#runtimeWorker"),
  runtimeWallet: document.querySelector("#runtimeWallet"),
  runtimeWalletToggle: document.querySelector("#runtimeWalletToggle"),
  poolHost: document.querySelector("#poolHost"),
  poolPort: document.querySelector("#poolPort"),
  poolTls: document.querySelector("#poolTls"),
  openMonitor: document.querySelector("#openMonitor"),
  startRuntimeBtn: document.querySelector("#startRuntimeBtn"),
  stopRuntimeBtn: document.querySelector("#stopRuntimeBtn"),
  runtimeMessage: document.querySelector("#runtimeMessage"),
  importProfileJson: document.querySelector("#importProfileJson"),
  plainTemplateBtn: document.querySelector("#plainTemplateBtn"),
  importProfileBtn: document.querySelector("#importProfileBtn"),
  importProfileStatus: document.querySelector("#importProfileStatus"),
  runtimeList: document.querySelector("#runtimeList"),
  gpuList: document.querySelector("#gpuList"),
  refreshBtn: document.querySelector("#refreshBtn"),
  admireBackgroundBtn: document.querySelector("#admireBackgroundBtn"),
  backgroundInput: document.querySelector("#backgroundInput"),
  resetBackgroundBtn: document.querySelector("#resetBackgroundBtn"),
  backgroundStatus: document.querySelector("#backgroundStatus"),
};

function t(key) {
  return I18N[state.lang]?.[key] || I18N.en[key] || key;
}

function setText(node, value) {
  if (node) node.textContent = value == null || value === "" ? "-" : String(value);
}

function applyLanguage() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.classList.toggle("active", button.dataset.lang === state.lang);
  });
  if (els.runtimeWalletToggle) {
    setText(els.runtimeWalletToggle, els.runtimeWallet?.type === "text" ? t("hide") : t("show"));
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body && !(options.body instanceof Blob) ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { ok: false, error: text || `HTTP ${response.status}` };
  }
  if (!response.ok) {
    const message = data.error || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

function plainTemplate() {
  return {
    id: "custom-plain-miner",
    label: "Custom Plain Miner",
    label_zh: "自定义 Plain Miner",
    kind: "plain",
    backend: "custom",
    cwd: "C:\\path\\to\\miner",
    command: ".\\miner.exe --pool {pool_host}:{pool_port} --wallet {wallet_address} --worker {worker} --gpu {gpu}",
    gpu: "0",
    pool_host: "pool.example.com",
    pool_port: "443",
    wallet_address: "prl1...",
    worker: "PapiMiner-plain",
    notes: "PlainProof-only profile. No model inference.",
  };
}

function currentProfile() {
  return state.profiles.find((profile) => profile.id === els.profileSelect.value) || state.profiles[0] || null;
}

function fillProfileFields(profile) {
  if (!profile) return;
  els.runtimeGpu.value = profile.gpu || "";
  els.runtimeWorker.value = profile.worker || "";
  els.runtimeWallet.value = profile.wallet_address || "";
  els.poolHost.value = profile.pool_host || "";
  els.poolPort.value = profile.pool_port || "";
  els.poolTls.checked = profile.pool_tls !== false;
}

function renderProfiles() {
  els.profileSelect.innerHTML = "";
  if (!state.profiles.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = t("noProfiles");
    els.profileSelect.append(option);
    return;
  }
  for (const profile of state.profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = state.lang === "zh" ? profile.label_zh || profile.label || profile.id : profile.label || profile.id;
    els.profileSelect.append(option);
  }
  fillProfileFields(currentProfile());
}

function fmt(value, suffix = "") {
  if (value == null || value === "") return "-";
  if (typeof value === "number") return `${Math.round(value * 10) / 10}${suffix}`;
  return `${value}${suffix}`;
}

function renderGpu() {
  const gpu = state.status?.gpu || [];
  if (!gpu.length) {
    setText(els.gpuList, state.status?.gpu_error || t("noGpu"));
    return;
  }
  els.gpuList.innerHTML = "";
  for (const item of gpu) {
    const row = document.createElement("div");
    row.className = "gpu-card";
    row.innerHTML = `
      <strong>GPU ${item.index}</strong>
      <span>${item.name || ""}</span>
      <b>${fmt(item.temperature_c, "C")}</b>
      <span>${fmt(item.power_w, "W")} / ${fmt(item.power_limit_w, "W")}</span>
      <span>${fmt(item.utilization_gpu_pct, "%")}</span>
      <span>${fmt(item.memory_used_mib, " MiB")} / ${fmt(item.memory_total_mib, " MiB")}</span>
    `;
    els.gpuList.append(row);
  }
}

function renderRuntime() {
  const processes = state.status?.runtime?.processes || [];
  if (!processes.length) {
    setText(els.runtimeList, t("noRuntime"));
    return;
  }
  els.runtimeList.innerHTML = "";
  for (const proc of processes) {
    const row = document.createElement("div");
    row.className = `runtime-card ${proc.running ? "running" : ""}`;
    const logLines = (proc.recent_log || []).slice(-5).map((line) => `<code>${escapeHtml(line)}</code>`).join("");
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(proc.profile_id || "-")}</strong>
        <span>${proc.running ? "RUNNING" : "STOPPED"} · pid ${proc.pid || "-"}</span>
      </div>
      <div>GPU ${escapeHtml(proc.gpu || "-")} · ${escapeHtml(proc.started_at || "-")}</div>
      <div class="log-tail">${logLines || "-"}</div>
    `;
    els.runtimeList.append(row);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function applyTheme(theme) {
  if (theme?.has_background && theme.background_url) {
    els.backgroundStage.style.backgroundImage = `url("${theme.background_url}")`;
  } else {
    els.backgroundStage.style.backgroundImage = "";
  }
}

async function refresh() {
  const [status, theme] = await Promise.all([api("/api/status"), api("/api/theme")]);
  state.status = status;
  state.profiles = status.run_profiles?.profiles || [];
  renderProfiles();
  renderGpu();
  renderRuntime();
  applyTheme(theme);
}

function overrides() {
  return {
    gpu: els.runtimeGpu.value.trim(),
    worker: els.runtimeWorker.value.trim(),
    wallet_address: els.runtimeWallet.value.trim(),
    pool_host: els.poolHost.value.trim(),
    pool_port: els.poolPort.value.trim(),
    pool_tls: els.poolTls.checked,
    open_monitor: els.openMonitor.checked,
  };
}

async function startRuntime() {
  const profile = currentProfile();
  if (!profile) return;
  try {
    const data = await api("/api/runtime/start", {
      method: "POST",
      body: JSON.stringify({ profile_id: profile.id, overrides: overrides() }),
    });
    setText(els.runtimeMessage, `${t("started")}: pid ${data.process?.pid || "-"}`);
    await refresh();
  } catch (error) {
    setText(els.runtimeMessage, `${t("startFailed")}: ${error.message}`);
  }
}

async function stopRuntime() {
  const profile = currentProfile();
  if (!profile) return;
  try {
    await api("/api/runtime/stop", {
      method: "POST",
      body: JSON.stringify({ profile_id: profile.id }),
    });
    setText(els.runtimeMessage, t("stopped"));
    await refresh();
  } catch (error) {
    setText(els.runtimeMessage, `${t("stopFailed")}: ${error.message}`);
  }
}

async function importProfile() {
  try {
    const profile = JSON.parse(els.importProfileJson.value || "{}");
    const data = await api("/api/import/profile", {
      method: "POST",
      body: JSON.stringify(profile),
    });
    setText(els.importProfileStatus, `${t("imported")}: ${data.profile?.id || "-"}`);
    await refresh();
  } catch (error) {
    setText(els.importProfileStatus, `${t("importFailed")}: ${error.message}`);
  }
}

async function uploadBackground(file) {
  if (!file) return;
  try {
    const data = await api("/api/theme/background", {
      method: "POST",
      headers: { "X-File-Name": encodeURIComponent(file.name) },
      body: file,
    });
    applyTheme(data.theme);
    setText(els.backgroundStatus, t("backgroundSaved"));
  } catch (error) {
    setText(els.backgroundStatus, error.message);
  }
}

async function resetBackground() {
  const data = await api("/api/theme/reset-background", { method: "POST" });
  applyTheme(data.theme);
  setText(els.backgroundStatus, t("backgroundReset"));
}

function bind() {
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => {
      state.lang = button.dataset.lang;
      localStorage.setItem("papiminer.lang", state.lang);
      applyLanguage();
      renderProfiles();
    });
  });
  els.profileSelect.addEventListener("change", () => fillProfileFields(currentProfile()));
  els.runtimeWalletToggle.addEventListener("click", () => {
    const visible = els.runtimeWallet.type === "text";
    els.runtimeWallet.type = visible ? "password" : "text";
    els.runtimeWalletToggle.setAttribute("aria-pressed", String(!visible));
    setText(els.runtimeWalletToggle, visible ? t("show") : t("hide"));
  });
  els.startRuntimeBtn.addEventListener("click", startRuntime);
  els.stopRuntimeBtn.addEventListener("click", stopRuntime);
  els.refreshBtn.addEventListener("click", refresh);
  els.plainTemplateBtn.addEventListener("click", () => {
    els.importProfileJson.value = JSON.stringify(plainTemplate(), null, 2);
  });
  els.importProfileBtn.addEventListener("click", importProfile);
  els.backgroundInput.addEventListener("change", () => uploadBackground(els.backgroundInput.files?.[0]));
  els.resetBackgroundBtn.addEventListener("click", resetBackground);
  els.admireBackgroundBtn.addEventListener("click", () => {
    state.admire = !state.admire;
    document.body.classList.toggle("admire", state.admire);
    els.admireBackgroundBtn.setAttribute("aria-pressed", String(state.admire));
  });
}

applyLanguage();
bind();
refresh().catch((error) => setText(els.runtimeMessage, error.message));
setInterval(() => refresh().catch(() => {}), 5000);
