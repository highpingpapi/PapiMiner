const state = {
  lang: localStorage.getItem("PapiMiner.lang") || "zh",
  view: localStorage.getItem("PapiMiner.view") || "dashboard",
  mode: "plain",
  models: [],
  modelDetails: [],
  registryModels: [],
  profiles: [],
  gpus: [],
  loadingProfiles: true,
  formProfileId: "",
  userEditedGpu: false,
  gpuOverrides: {
    plain: localStorage.getItem("PapiMiner.gpu.plain") || "",
    useful: localStorage.getItem("PapiMiner.gpu.useful") || "",
  },
  runtime: null,
  metrics: null,
  theme: null,
  evidence: null,
  selectedModel: localStorage.getItem("PapiMiner.selectedModel") || "",
  busy: false,
  walletVisible: localStorage.getItem("PapiMiner.walletVisible") === "1",
  backgroundFocus: localStorage.getItem("PapiMiner.backgroundFocus") === "1",
};

let backgroundFocusLockTimer = 0;

const i18n = {
  zh: {
    eyebrow: "Pearl 本地控制台",
    subhead: "导入模型，启动 plain 挖矿或 useful-work，并把每次推理的证据摊开给你看。",
    checking: "检查中",
    refresh: "刷新",
    admireBackground: "欣赏背景",
    exitBackground: "退出欣赏",
    viewDashboard: "\u63a7\u5236\u53f0",
    viewChat: "\u5bf9\u8bdd",
    importTitle: "导入中心",
    importDesc: "模型路径和运行档案只写入 local/，适合以后开源时保留干净代码。",
    importModel: "导入模型路径",
    modelId: "模型名称",
    modelPath: "本地模型路径",
    importBtn: "导入",
    browseFolder: "选文件夹",
    browseFile: "选文件",
    browseJson: "选择档案文件",
    profilePickerHint: "Miner 通过运行档案导入，全部写入 local/。空着直接点导入，会先弹出 JSON 文件选择窗口。",
    plainMinerTemplate: "Plain miner 模板",
    usefulMinerTemplate: "Useful miner 模板",
    customMinerTemplate: "自定义命令模板",
    templateLoaded: "模板已填入，确认路径和参数后再导入",
    choosing: "打开选择窗口...",
    chooserCancelled: "已取消选择",
    chooserFailed: "选择失败",
    privacyCheck: "隐私检查",
    privacyWallet: "钱包地址、worker 名：local-only",
    privacyPath: "内网路径、机器名、日志路径：local-only",
    privacySecret: "助记词、私钥、交易所密码：永不保存",
    profileJson: "导入 Miner / 运行档案 JSON",
    importProfile: "导入已选档案",
    runTitle: "运行控制",
    runDesc: "Plain 和 Useful 默认不能抢同一张 GPU。Useful 默认是“本地请求 + 连接矿池挖 PRL”，不是池子派单。",
    profile: "运行档案",
    gpuLabel: "GPU(s)",
    gpuPlaceholder: "0 或 0,1,2",
    gpuPickerIntro: "点击显卡卡片来自主选择要跑的 GPU，可多选；启动时只会使用选中的卡。",
    gpuOverrideNote: "这里的选择会覆盖运行档案里的默认 GPU；清空则回到档案默认值。",
    manualGpu: "手动输入",
    gpuPickerHint: "未检测到 GPU，仍可手填 0,1。",
    selectTwoGpus: "双卡 0,1",
    selectAllGpus: "全卡运行",
    clearGpus: "清空选择",
    selectedGpus: "启动时使用",
    noGpuSelected: "未手动选择 GPU，使用档案默认值",
    profileDefaultGpus: "档案默认使用",
    noProfileDefaultGpus: "未手动选择 GPU，且档案没有默认 GPU",
    gpuChipOn: "已选中",
    gpuChipOff: "点击选择",
    runningOnGpu: "运行中",
    gpuFallback0: "手动 GPU 0",
    gpuFallback1: "手动 GPU 1",
    gpuManualCard: "未读取到实时状态，仍可作为启动目标",
    useThisGpu: "用于本次启动",
    skipThisGpu: "本次不使用",
    tensorParallel: "TP size / 张量并行",
    tensorParallelHint: "Useful 多 GPU 时需要；留空会按所选 GPU 数自动填。混合显卡可能受最小显存限制。",
    usefulRouteTitle: "Useful 连接方式",
    routePoolLocalTitle: "连接矿池 + 本地推理",
    routePoolLocalDesc: "默认：连接矿池拿 job，本地提问可能提交 PRL share。参数：--inference-stream-mode reserved。",
    routeLocalTitle: "只本地推理",
    routeLocalDesc: "不连接矿池，不提交 share，基本没有 PRL 收益。参数：--no-pool。",
    routePoolRoutedTitle: "连接矿池 + 接受池子派单",
    routePoolRoutedDesc: "允许 Akoya pool 把外部请求派到你的机器。参数：--inference-stream-mode pool。默认不建议开。",
    openMonitor: "启动时打开监控弹窗：温度、功耗、利用率、核心频率、GPU 进程、最近日志和 useful metrics。",
    wallet: "PRL 地址",
    runtimeModel: "Useful 模型",
    noPool: "离线推理：不连矿池（无 PRL share）",
    poolRouted: "额外接受池子派单（外部请求，默认关）",
    plainRevenueHint: "Plain 挖矿：连接矿池并提交 share，才有 PRL 收益；这里不提供本地聊天。",
    usefulPoolHint: "Useful 默认模式：连接矿池拿 mining job，但只处理你本地发起的推理请求；你的本地提问如果触发 Pearl useful GEMM，就可能提交 PRL share。",
    usefulLocalHint: "离线推理模式：只给你本地聊天/测试，不连接矿池，不提交 share，预期没有 PRL 收益。",
    usefulPoolRoutedHint: "Useful + 池子派单：在“本地请求 + 矿池挖 PRL”之外，额外允许 Akoya pool 派外部推理请求到你的机器；默认应谨慎开启。",
    noProfileHint: "当前模式没有可用运行档案，先导入或等待内置档案加载；启动按钮会保持禁用。",
    profilesLoadingHint: "正在读取运行档案。读取完成前不会启动任何 miner。",
    start: "启动",
    stop: "停止",
    chatTitle: "模型对话",
    chatDesc: "发送一次本地请求，PapiMiner 会记录 GEMM、CAPI、launch 和 share 的前后差值。",
    currentModel: "当前模型",
    modelSelectedInRunControl: "在运行控制里选择模型；对话页只显示当前模型。",
    modelLabel: "模型",
    emptyState: "Akoya/vLLM 开起来之后，这里就能聊天并观察 useful-work 证据。",
    promptPlaceholder: "比如：解释 Pearl useful work 和普通挖矿的区别",
    send: "发送",
    evidenceTitle: "Useful 在哪",
    evidenceDesc: "每次推理后的证据卡。",
    runtimeTitle: "运行进程",
    updatedAt: "更新时间",
    modelPathTitle: "模型路径",
    selectedModel: "当前模型",
    localPath: "本地路径",
    pathStatus: "路径状态",
    loading: "读取中...",
    appearance: "外观",
    chooseBackground: "选择背景图",
    resetBackground: "重置背景",
    noModel: "暂无模型",
    noProfile: "没有可用档案",
    profilesLoading: "运行档案加载中...",
    noRuntime: "暂无运行进程",
    noGpu: "没有读到 GPU",
    healthOnline: "vLLM online",
    healthOffline: "vLLM 未连接",
    roleUser: "你",
    roleAssistant: "PapiMiner",
    thinking: "思考中...",
    requestFailed: "请求失败",
    emptyOutput: "(empty)",
    pathKnown: "已登记",
    pathUnknown: "未登记",
    pathExists: "存在",
    pathMissing: "路径不存在",
    pathComplete: "权重完整",
    pathIncomplete: "权重不完整",
    backgroundReady: "当前背景",
    backgroundNone: "未设置本地背景",
    backgroundUploading: "正在上传背景图...",
    backgroundUploaded: "背景图已更新",
    backgroundUploadFailed: "背景图上传失败",
    imported: "已导入",
    importFailed: "导入失败",
    started: "已启动",
    stopped: "已停止",
    noEvidence: "还没有请求证据",
    noWarnings: "暂时没有明显阻断原因",
  },
  en: {
    eyebrow: "Pearl local console",
    subhead: "Import models, start plain mining or useful work, and inspect evidence for every inference request.",
    checking: "checking",
    refresh: "Refresh",
    admireBackground: "Admire Background",
    exitBackground: "Exit View",
    viewDashboard: "Dashboard",
    viewChat: "Chat",
    importTitle: "Import Center",
    importDesc: "Model paths and run profiles are written only to local/ so the open-source tree stays clean.",
    importModel: "Import Model Path",
    modelId: "Model name",
    modelPath: "Local model path",
    importBtn: "Import",
    browseFolder: "Folder",
    browseFile: "File",
    browseJson: "Choose Profile File",
    profilePickerHint: "Miners are imported as run profiles and stored in local/. If the editor is empty, Import opens a JSON file picker first.",
    plainMinerTemplate: "Plain miner template",
    usefulMinerTemplate: "Useful miner template",
    customMinerTemplate: "Custom command template",
    templateLoaded: "Template inserted. Check paths and args before importing.",
    choosing: "Opening picker...",
    chooserCancelled: "Selection cancelled",
    chooserFailed: "Picker failed",
    privacyCheck: "Privacy Check",
    privacyWallet: "Wallet address and worker name: local-only",
    privacyPath: "LAN paths, machine names, and logs: local-only",
    privacySecret: "Seed phrases, private keys, and exchange passwords: never stored",
    profileJson: "Import Miner / Run profile JSON",
    importProfile: "Import Selected Profile",
    runTitle: "Run Control",
    runDesc: "Plain and Useful do not share the same GPU by default. Useful defaults to local requests + pool mining, not pool-routed jobs.",
    profile: "Run profile",
    gpuLabel: "GPU(s)",
    gpuPlaceholder: "0 or 0,1,2",
    gpuPickerIntro: "Click GPU cards to choose exactly which GPUs run. Multi-select works; Start uses only the selected cards.",
    gpuOverrideNote: "This overrides the run profile default GPU list; clear it to fall back to the profile default.",
    manualGpu: "Manual",
    gpuPickerHint: "No GPU detected yet. You can still type 0,1.",
    selectTwoGpus: "Dual 0,1",
    selectAllGpus: "Run all GPUs",
    clearGpus: "Clear selection",
    selectedGpus: "Start will use",
    noGpuSelected: "No manual GPU selection; using the profile default",
    profileDefaultGpus: "Profile default",
    noProfileDefaultGpus: "No manual GPU selection and the profile has no default GPU",
    gpuChipOn: "Selected",
    gpuChipOff: "Click to select",
    runningOnGpu: "Running",
    gpuFallback0: "Manual GPU 0",
    gpuFallback1: "Manual GPU 1",
    gpuManualCard: "Live status unavailable; still usable as a start target",
    useThisGpu: "Use for this run",
    skipThisGpu: "Skip this run",
    tensorParallel: "TP size / tensor parallel",
    tensorParallelHint: "Required for Useful multi-GPU. Leave blank to use the selected GPU count. Mixed GPUs may be limited by the smallest VRAM device.",
    usefulRouteTitle: "Useful connection mode",
    routePoolLocalTitle: "Pool + local inference",
    routePoolLocalDesc: "Default: connect to the pool for jobs; local prompts may submit PRL shares. Flag: --inference-stream-mode reserved.",
    routeLocalTitle: "Local inference only",
    routeLocalDesc: "No pool connection, no share submission, and no expected PRL rewards. Flag: --no-pool.",
    routePoolRoutedTitle: "Pool + pool-routed requests",
    routePoolRoutedDesc: "Allow Akoya pool to route external requests to your machine. Flag: --inference-stream-mode pool. Keep this off by default.",
    openMonitor: "Open monitor window on start: temperature, power, utilization, core clocks, GPU processes, recent logs, and useful metrics.",
    wallet: "PRL address",
    runtimeModel: "Useful model",
    noPool: "Offline inference: no pool (no PRL shares)",
    poolRouted: "Also accept pool-routed jobs (external requests, off by default)",
    plainRevenueHint: "Plain mining: connects to a pool and submits shares for PRL rewards; it does not provide local chat.",
    usefulPoolHint: "Useful default: connect to the pool for mining jobs, but only serve your local inference requests. If your local prompts trigger Pearl useful GEMM, the miner may submit PRL shares.",
    usefulLocalHint: "Offline inference: local chat/testing only, no pool connection, no share submission, and no expected PRL rewards.",
    usefulPoolRoutedHint: "Useful + pool-routed jobs: in addition to local requests + pool mining, Akoya pool may send external inference requests to your machine. Keep this opt-in.",
    noProfileHint: "No run profile is available for the current mode yet. Import one or wait for built-ins to load; Start stays disabled.",
    profilesLoadingHint: "Reading run profiles. No miner will be started before loading finishes.",
    start: "Start",
    stop: "Stop",
    chatTitle: "Model Chat",
    chatDesc: "Send a local request and PapiMiner records GEMM, CAPI, launch, and share deltas.",
    currentModel: "Current model",
    modelSelectedInRunControl: "Choose the model in Run Control; Chat only shows the active choice.",
    modelLabel: "Model",
    emptyState: "Once Akoya/vLLM is running, you can chat here and inspect useful-work evidence.",
    promptPlaceholder: "Example: explain Pearl useful work",
    send: "Send",
    evidenceTitle: "Where Is Useful",
    evidenceDesc: "Evidence card after each inference request.",
    runtimeTitle: "Runtime",
    updatedAt: "Updated",
    modelPathTitle: "Model Path",
    selectedModel: "Selected Model",
    localPath: "Local Path",
    pathStatus: "Path Status",
    loading: "Loading...",
    appearance: "Appearance",
    chooseBackground: "Choose Background",
    resetBackground: "Reset Background",
    noModel: "No models",
    noProfile: "No profiles",
    profilesLoading: "Loading run profiles...",
    noRuntime: "No running process",
    noGpu: "No GPU detected",
    healthOnline: "vLLM online",
    healthOffline: "vLLM offline",
    roleUser: "You",
    roleAssistant: "PapiMiner",
    thinking: "Thinking...",
    requestFailed: "Request failed",
    emptyOutput: "(empty)",
    pathKnown: "Registered",
    pathUnknown: "Not registered",
    pathExists: "exists",
    pathMissing: "missing",
    pathComplete: "weights complete",
    pathIncomplete: "weights incomplete",
    backgroundReady: "Current background",
    backgroundNone: "No local background",
    backgroundUploading: "Uploading background...",
    backgroundUploaded: "Background updated",
    backgroundUploadFailed: "Background upload failed",
    imported: "Imported",
    importFailed: "Import failed",
    started: "Started",
    stopped: "Stopped",
    noEvidence: "No request evidence yet",
    noWarnings: "No obvious blocker right now",
  },
};

const els = {
  healthPill: document.querySelector("#healthPill"),
  langButtons: document.querySelectorAll("[data-lang]"),
  viewButtons: document.querySelectorAll("button[data-view]"),
  admireBackgroundBtn: document.querySelector("#admireBackgroundBtn"),
  refreshBtn: document.querySelector("#refreshBtn"),
  importModelId: document.querySelector("#importModelId"),
  importModelPath: document.querySelector("#importModelPath"),
  browseModelFolderBtn: document.querySelector("#browseModelFolderBtn"),
  browseModelFileBtn: document.querySelector("#browseModelFileBtn"),
  importModelBtn: document.querySelector("#importModelBtn"),
  importModelStatus: document.querySelector("#importModelStatus"),
  importProfileJson: document.querySelector("#importProfileJson"),
  browseProfileJsonBtn: document.querySelector("#browseProfileJsonBtn"),
  importProfileBtn: document.querySelector("#importProfileBtn"),
  importProfileStatus: document.querySelector("#importProfileStatus"),
  profileTemplateButtons: document.querySelectorAll("[data-profile-template]"),
  modeButtons: document.querySelectorAll("button[data-mode]"),
  profileSelect: document.querySelector("#profileSelect"),
  runtimeGpu: document.querySelector("#runtimeGpu"),
  runtimeTensorParallel: document.querySelector("#runtimeTensorParallel"),
  gpuPicker: document.querySelector("#gpuPicker"),
  selectTwoGpusBtn: document.querySelector("#selectTwoGpusBtn"),
  selectAllGpusBtn: document.querySelector("#selectAllGpusBtn"),
  clearGpusBtn: document.querySelector("#clearGpusBtn"),
  gpuSelectionStatus: document.querySelector("#gpuSelectionStatus"),
  routeButtons: document.querySelectorAll("[data-useful-route]"),
  runtimeWorker: document.querySelector("#runtimeWorker"),
  runtimeWallet: document.querySelector("#runtimeWallet"),
  runtimeWalletToggle: document.querySelector("#runtimeWalletToggle"),
  runtimeModel: document.querySelector("#runtimeModel"),
  runtimeNoPool: document.querySelector("#runtimeNoPool"),
  poolRouted: document.querySelector("#poolRouted"),
  openMonitor: document.querySelector("#openMonitor"),
  runRevenueHint: document.querySelector("#runRevenueHint"),
  startRuntimeBtn: document.querySelector("#startRuntimeBtn"),
  stopRuntimeBtn: document.querySelector("#stopRuntimeBtn"),
  runtimeMessage: document.querySelector("#runtimeMessage"),
  modelSelect: document.querySelector("#modelSelect"),
  chatCurrentModel: document.querySelector("#chatCurrentModel"),
  maxTokens: document.querySelector("#maxTokens"),
  temperature: document.querySelector("#temperature"),
  chatLog: document.querySelector("#chatLog"),
  chatForm: document.querySelector("#chatForm"),
  promptInput: document.querySelector("#promptInput"),
  sendBtn: document.querySelector("#sendBtn"),
  evidenceVerdict: document.querySelector("#evidenceVerdict"),
  evidenceGemms: document.querySelector("#evidenceGemms"),
  evidenceCapi: document.querySelector("#evidenceCapi"),
  evidenceLaunches: document.querySelector("#evidenceLaunches"),
  evidenceShares: document.querySelector("#evidenceShares"),
  evidenceKernel: document.querySelector("#evidenceKernel"),
  evidenceTokens: document.querySelector("#evidenceTokens"),
  evidenceHashrate: document.querySelector("#evidenceHashrate"),
  evidenceReasons: document.querySelector("#evidenceReasons"),
  layerList: document.querySelector("#layerList"),
  runtimeList: document.querySelector("#runtimeList"),
  apiBase: document.querySelector("#apiBase"),
  updateTime: document.querySelector("#updateTime"),
  usefulHashrate: document.querySelector("#usefulHashrate"),
  poolRegistered: document.querySelector("#poolRegistered"),
  poolStream: document.querySelector("#poolStream"),
  jobsReceived: document.querySelector("#jobsReceived"),
  shareTotals: document.querySelector("#shareTotals"),
  kernelTotals: document.querySelector("#kernelTotals"),
  miningEnabled: document.querySelector("#miningEnabled"),
  selectedModelInfo: document.querySelector("#selectedModelInfo"),
  selectedModelPath: document.querySelector("#selectedModelPath"),
  selectedModelPathStatus: document.querySelector("#selectedModelPathStatus"),
  gpuList: document.querySelector("#gpuList"),
  backgroundInput: document.querySelector("#backgroundInput"),
  resetBackgroundBtn: document.querySelector("#resetBackgroundBtn"),
  backgroundStatus: document.querySelector("#backgroundStatus"),
  backgroundStage: document.querySelector("#backgroundStage"),
};

function t(key) {
  return i18n[state.lang]?.[key] || i18n.zh[key] || key;
}

function fmt(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function setText(node, value) {
  if (node) node.textContent = value ?? "-";
}

function walletToggleLabel() {
  if (state.lang === "en") return state.walletVisible ? "Hide" : "Show";
  return state.walletVisible ? "隐藏" : "显示";
}

function syncWalletVisibility() {
  if (!els.runtimeWallet || !els.runtimeWalletToggle) return;
  els.runtimeWallet.type = state.walletVisible ? "text" : "password";
  els.runtimeWalletToggle.textContent = walletToggleLabel();
  els.runtimeWalletToggle.setAttribute("aria-pressed", state.walletVisible ? "true" : "false");
  els.runtimeWalletToggle.setAttribute("aria-label", walletToggleLabel());
}

function toggleWalletVisibility() {
  state.walletVisible = !state.walletVisible;
  localStorage.setItem("PapiMiner.walletVisible", state.walletVisible ? "1" : "0");
  syncWalletVisibility();
}

function escapeHtml(value) {
  return String(value ?? "-")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function runtimeLabel(key) {
  const labels = {
    zh: {
      age: "\u8fd0\u884c\u65f6\u957f",
      health: "vLLM",
      poolJob: "\u77ff\u6c60 job",
      next: "\u5efa\u8bae\u52a8\u4f5c",
      error: "\u6700\u8fd1\u9519\u8bef",
      log: "\u6700\u8fd1\u65e5\u5fd7",
      path: "\u65e5\u5fd7\u8def\u5f84",
      monitor: "\u76d1\u63a7\u7a97\u53e3",
      yes: "\u6709",
      no: "\u65e0",
      online: "\u5728\u7ebf",
      offline: "\u672a\u8fde\u63a5",
      gpu: "GPU",
    },
    en: {
      age: "Uptime",
      health: "vLLM",
      poolJob: "Pool job",
      next: "Suggested action",
      error: "Recent error",
      log: "Recent logs",
      path: "Log path",
      monitor: "Monitor",
      yes: "yes",
      no: "no",
      online: "online",
      offline: "offline",
      gpu: "GPU",
    },
  };
  return labels[state.lang]?.[key] || labels.en[key] || key;
}

function formatAge(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0) return "-";
  if (value < 60) return `${Math.floor(value)}s`;
  const minutes = Math.floor(value / 60);
  if (minutes < 60) return `${minutes}m ${Math.floor(value % 60)}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function diagnosticField(diagnostic, field) {
  if (!diagnostic) return "";
  if (state.lang === "en") return diagnostic[`${field}_en`] || diagnostic[field] || "";
  return diagnostic[field] || diagnostic[`${field}_en`] || "";
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const localized = state.lang === "en" ? data.error_en || data.error : data.error || data.error_en;
    const detail = data.detail && !localized ? data.detail : "";
    throw new Error(localized || detail || `HTTP ${response.status}`);
  }
  return data;
}

function applyI18n() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  for (const node of document.querySelectorAll("[data-i18n]")) {
    node.textContent = t(node.dataset.i18n);
  }
  for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
    node.setAttribute("placeholder", t(node.dataset.i18nPlaceholder));
  }
  for (const button of els.langButtons) {
    button.classList.toggle("active", button.dataset.lang === state.lang);
  }
  applyView();
  applyBackgroundFocus();
  initProfilePlaceholder();
  renderProfiles();
  renderModelOptions();
  renderSelectedModelPath();
  renderEvidence(state.evidence);
  renderRuntime();
  renderBackgroundStatus(state.theme);
  syncWalletVisibility();
}

function setLanguage(lang) {
  state.lang = lang;
  localStorage.setItem("PapiMiner.lang", lang);
  applyI18n();
}

function applyView() {
  document.body.dataset.view = state.view;
  for (const button of els.viewButtons) {
    button.classList.toggle("active", button.dataset.view === state.view);
  }
}

function setView(view) {
  state.view = view === "chat" ? "chat" : "dashboard";
  localStorage.setItem("PapiMiner.view", state.view);
  applyView();
}

function backgroundFocusLabel() {
  return state.backgroundFocus ? t("exitBackground") : t("admireBackground");
}

function applyBackgroundFocus() {
  window.clearTimeout(backgroundFocusLockTimer);
  document.body.classList.remove("background-admire-locked");
  document.body.classList.toggle("background-admire", state.backgroundFocus);
  if (state.backgroundFocus) {
    backgroundFocusLockTimer = window.setTimeout(() => {
      if (state.backgroundFocus) document.body.classList.add("background-admire-locked");
    }, 560);
  }
  if (!els.admireBackgroundBtn) return;
  els.admireBackgroundBtn.textContent = backgroundFocusLabel();
  els.admireBackgroundBtn.setAttribute("aria-pressed", state.backgroundFocus ? "true" : "false");
}

function toggleBackgroundFocus() {
  state.backgroundFocus = !state.backgroundFocus;
  localStorage.setItem("PapiMiner.backgroundFocus", state.backgroundFocus ? "1" : "0");
  applyBackgroundFocus();
}

function setHealth(online, error) {
  els.healthPill.className = `status-pill ${online ? "online" : "offline"}`;
  els.healthPill.textContent = online ? t("healthOnline") : `${t("healthOffline")}${error ? ": " + error : ""}`;
}

function displayName(profile) {
  return state.lang === "zh" ? profile.label_zh || profile.label || profile.id : profile.label || profile.label_zh || profile.id;
}

function currentProfile() {
  return state.profiles.find((profile) => profile.id === els.profileSelect.value);
}

function renderProfiles() {
  const previous = els.profileSelect.value;
  const profiles = state.profiles.filter((profile) => profile.kind === state.mode || profile.kind === "custom");
  els.profileSelect.innerHTML = "";
  if (!profiles.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = state.loadingProfiles ? t("profilesLoading") : t("noProfile");
    els.profileSelect.append(option);
    syncProfileForm();
    return;
  }
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    const audit = profile.audit === "open-source upstream" ? "open" : "custom";
    option.textContent = `${displayName(profile)} · ${audit}`;
    els.profileSelect.append(option);
  }
  if (profiles.some((profile) => profile.id === previous)) {
    els.profileSelect.value = previous;
  }
  if (els.profileSelect.value !== state.formProfileId) {
    syncProfileForm();
  } else {
    renderGpuPicker();
    syncModeControls();
  }
}

function renderRunRevenueHint() {
  if (!els.runRevenueHint) return;
  let key = state.loadingProfiles && !currentProfile() ? "profilesLoadingHint" : currentProfile() ? "plainRevenueHint" : "noProfileHint";
  if (state.mode === "useful") {
    if (state.loadingProfiles && !currentProfile()) key = "profilesLoadingHint";
    else if (!currentProfile()) key = "noProfileHint";
    else if (els.runtimeNoPool.checked) key = "usefulLocalHint";
    else if (els.poolRouted.checked) key = "usefulPoolRoutedHint";
    else key = "usefulPoolHint";
  }
  els.runRevenueHint.textContent = t(key);
  els.runRevenueHint.dataset.mode = !currentProfile() || (state.mode === "useful" && els.runtimeNoPool.checked) ? "local" : state.mode;
}

function currentUsefulRoute() {
  if (els.runtimeNoPool.checked) return "local";
  if (els.poolRouted.checked) return "pool-routed";
  return "pool-local";
}

function renderUsefulRoute() {
  const usefulMode = state.mode === "useful";
  const hasProfile = Boolean(currentProfile());
  const activeRoute = currentUsefulRoute();
  for (const button of els.routeButtons) {
    const active = button.dataset.usefulRoute === activeRoute;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.disabled = !usefulMode || !hasProfile;
  }
}

function setUsefulRoute(route) {
  if (route === "local") {
    els.runtimeNoPool.checked = true;
    els.poolRouted.checked = false;
  } else if (route === "pool-routed") {
    els.runtimeNoPool.checked = false;
    els.poolRouted.checked = true;
  } else {
    els.runtimeNoPool.checked = false;
    els.poolRouted.checked = false;
  }
  renderUsefulRoute();
  renderRunRevenueHint();
}

function syncModeControls() {
  const usefulMode = state.mode === "useful";
  const hasProfile = Boolean(currentProfile());
  els.runtimeNoPool.disabled = !usefulMode || !hasProfile;
  els.poolRouted.disabled = !usefulMode || !hasProfile || els.runtimeNoPool.checked;
  els.startRuntimeBtn.disabled = !hasProfile;
  if (!usefulMode) {
    els.runtimeNoPool.checked = false;
    els.poolRouted.checked = false;
  }
  if (els.runtimeNoPool.checked) {
    els.poolRouted.checked = false;
  }
  renderUsefulRoute();
  renderRunRevenueHint();
}

function renderModelOptions() {
  const onlineModels = state.models.map((id) => ({ value: id, label: id, source: "vLLM" }));
  const registered = state.registryModels.map((model) => ({
    value: model.path || model.id,
    label: `${model.id} · ${model.exists ? t("pathExists") : t("pathMissing")} · ${
      model.integrity?.complete === true ? t("pathComplete") : t("pathIncomplete")
    }`,
    source: "local",
    complete: model.exists && model.integrity?.complete === true,
  }));
  const options = [...onlineModels, ...registered];
  const previous = state.selectedModel || els.modelSelect.value || els.runtimeModel.value || currentProfile()?.model || "";
  for (const select of [els.modelSelect, els.runtimeModel]) {
    select.innerHTML = "";
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("noModel");
      select.append(option);
      continue;
    }
    for (const item of options) {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      select.append(option);
    }
  }
  const values = new Set(options.map((item) => item.value));
  const completeValues = new Set(options.filter((item) => item.source !== "local" || item.complete).map((item) => item.value));
  const profileModel = currentProfile()?.model || "";
  let next = "";
  if (completeValues.has(previous)) next = previous;
  else if (values.has(previous) && !completeValues.size) next = previous;
  else if (values.has(profileModel)) next = profileModel;
  else if (onlineModels.length) next = onlineModels[0].value;
  else if (registered.some((item) => item.complete)) next = registered.find((item) => item.complete).value;
  else if (options.length) next = options[0].value;
  setSelectedModel(next, { persist: Boolean(next) });
}

function hasSelectOption(select, value) {
  return [...select.options].some((option) => option.value === value);
}

function modelDisplayName(value) {
  const modelId = String(value || "");
  if (!modelId) return "-";
  const detail = state.modelDetails.find((item) => item.id === modelId || item.path === modelId);
  if (detail?.id) return detail.id;
  const registry = state.registryModels.find((item) => item.id === modelId || item.path === modelId);
  if (registry?.id) return registry.id;
  return basename(modelId) || modelId;
}

function setSelectedModel(value, { persist = true } = {}) {
  const next = String(value || "");
  state.selectedModel = next;
  if (persist) {
    if (next) localStorage.setItem("PapiMiner.selectedModel", next);
    else localStorage.removeItem("PapiMiner.selectedModel");
  }
  for (const select of [els.modelSelect, els.runtimeModel]) {
    if (hasSelectOption(select, next)) select.value = next;
  }
  if (els.chatCurrentModel) {
    els.chatCurrentModel.textContent = modelDisplayName(next);
    els.chatCurrentModel.title = next;
  }
  renderSelectedModelPath();
}

function detectedGpuIndices() {
  return state.gpus.map((gpu) => String(gpu.index)).filter((index) => index !== "");
}

function fallbackGpuOptions() {
  return [
    { index: "0", name: t("gpuFallback0"), manual: true },
    { index: "1", name: t("gpuFallback1"), manual: true },
  ];
}

function selectableGpuOptions() {
  return state.gpus?.length ? state.gpus : fallbackGpuOptions();
}

function selectableGpuIndices() {
  return selectableGpuOptions().map((gpu) => String(gpu.index)).filter((index) => index !== "");
}

function parseGpuSelection(value) {
  const text = String(value || "").trim().toLowerCase();
  const detected = selectableGpuIndices();
  if (text === "all" || text === "*") return new Set(detected);
  const selected = new Set();
  for (const token of text.split(/[,\s]+/)) {
    if (!token) continue;
    if (/^\d+-\d+$/.test(token)) {
      const [start, end] = token.split("-").map(Number);
      if (start <= end && end - start <= 32) {
        for (let index = start; index <= end; index += 1) selected.add(String(index));
      }
      continue;
    }
    selected.add(token);
  }
  return selected;
}

function sortedGpuSelection(selected) {
  return [...selected].sort((left, right) => {
    const leftNum = Number(left);
    const rightNum = Number(right);
    if (Number.isFinite(leftNum) && Number.isFinite(rightNum)) return leftNum - rightNum;
    return String(left).localeCompare(String(right));
  });
}

function setGpuSelection(indices) {
  state.userEditedGpu = true;
  els.runtimeGpu.value = indices.join(",");
  state.gpuOverrides[state.mode] = els.runtimeGpu.value;
  localStorage.setItem(`PapiMiner.gpu.${state.mode}`, els.runtimeGpu.value);
  renderGpuPicker();
}

function runningGpuMap() {
  const running = new Map();
  const processes = state.runtime?.processes || [];
  for (const process of processes) {
    if (!process?.running) continue;
    const gpuSet = parseGpuSelection(process.gpu);
    for (const index of gpuSet) {
      running.set(index, process.profile_id || process.kind || "runtime");
    }
  }
  return running;
}

function renderGpuSelectionStatus(selected = parseGpuSelection(els.runtimeGpu.value)) {
  if (!els.gpuSelectionStatus) return;
  const list = sortedGpuSelection(selected);
  if (list.length) {
    els.gpuSelectionStatus.textContent = `${t("selectedGpus")}: GPU ${list.join(", GPU ")}`;
    return;
  }
  const profileGpu = String(currentProfile()?.gpu || "").trim();
  els.gpuSelectionStatus.textContent = profileGpu
    ? `${t("noGpuSelected")} · ${t("profileDefaultGpus")}: GPU ${profileGpu}`
    : t("noProfileDefaultGpus");
}

function renderGpuPicker() {
  if (!els.gpuPicker) return;
  const gpus = selectableGpuOptions();
  const hasLiveGpu = Boolean(state.gpus?.length);
  const selected = parseGpuSelection(els.runtimeGpu.value);
  const running = runningGpuMap();
  renderGpuSelectionStatus(selected);
  els.gpuPicker.innerHTML = "";
  if (!gpus.length) {
    const hint = document.createElement("span");
    hint.className = "gpu-picker-hint";
    hint.textContent = t("gpuPickerHint");
    els.gpuPicker.append(hint);
    return;
  }
  for (const gpu of gpus) {
    const index = String(gpu.index);
    const runningProfile = running.get(index);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `gpu-chip ${selected.has(index) ? "active" : ""} ${runningProfile ? "running" : ""} ${gpu.manual ? "manual" : ""}`;
    button.dataset.gpuIndex = index;
    button.setAttribute("aria-pressed", selected.has(index) ? "true" : "false");
    button.title = `${selected.has(index) ? t("gpuChipOn") : t("gpuChipOff")} GPU ${index}${runningProfile ? ` · ${t("runningOnGpu")}: ${runningProfile}` : ""}`;
    const title = document.createElement("strong");
    title.textContent = `GPU ${index}`;
    const name = document.createElement("em");
    name.textContent = gpu.name || "GPU";
    const stats = document.createElement("span");
    const watts = Number(gpu.power_w);
    const limit = Number(gpu.power_limit_w);
    const memoryUsed = Number(gpu.memory_used_mib);
    const memoryTotal = Number(gpu.memory_total_mib);
    const memoryLabel = Number.isFinite(memoryUsed) && Number.isFinite(memoryTotal)
      ? ` \u00b7 ${(memoryUsed / 1024).toFixed(1)}/${(memoryTotal / 1024).toFixed(0)}GB`
      : "";
    stats.textContent = hasLiveGpu
      ? `${gpu.temp_c ?? "-"}C \u00b7 ${gpu.util_pct ?? "-"}% \u00b7 ${Number.isFinite(watts) ? watts.toFixed(0) : "-"}W${Number.isFinite(limit) ? " / " + limit.toFixed(0) + "W" : ""}${memoryLabel}`
      : t("gpuManualCard");
    const role = document.createElement("span");
    role.className = "gpu-chip-role";
    role.textContent = selected.has(index) ? t("useThisGpu") : t("skipThisGpu");
    const stateBadge = document.createElement("span");
    stateBadge.className = "gpu-chip-state";
    stateBadge.textContent = runningProfile
      ? `${t("runningOnGpu")}: ${runningProfile}`
      : selected.has(index) ? t("gpuChipOn") : t("gpuChipOff");
    button.append(title, name, stats, role, stateBadge);
    els.gpuPicker.append(button);
  }
}

function toggleGpuIndex(index) {
  const selected = parseGpuSelection(els.runtimeGpu.value);
  if (selected.has(index)) selected.delete(index);
  else selected.add(index);
  setGpuSelection(sortedGpuSelection(selected));
}

function syncProfileForm() {
  const profile = currentProfile();
  if (!profile) {
    state.formProfileId = "";
    els.runtimeGpu.value = "";
    els.runtimeWorker.value = "";
    renderGpuPicker();
    syncModeControls();
    return;
  }
  state.formProfileId = profile.id;
  els.runtimeGpu.value = state.gpuOverrides[state.mode] || profile.gpu || "";
  if (els.runtimeTensorParallel) {
    els.runtimeTensorParallel.value = profile.tensor_parallel_size || "";
  }
  renderGpuPicker();
  els.runtimeWorker.value = profile.worker || "";
  if (profile.wallet_address) els.runtimeWallet.value = profile.wallet_address;
  els.runtimeNoPool.checked = Boolean(profile.no_pool) || profile.connect_pool === false;
  els.poolRouted.checked = Boolean(profile.pool_routed);
  if (profile.model && !state.selectedModel) {
    setSelectedModel(profile.model, { persist: false });
  } else {
    setSelectedModel(state.selectedModel, { persist: false });
  }
  syncModeControls();
}

function renderSelectedModelPath() {
  const modelId = state.selectedModel || els.modelSelect.value || els.runtimeModel.value || "";
  const detail = state.modelDetails.find((item) => item.id === modelId);
  const registry = detail?.registry || state.registryModels.find((item) => item.path === modelId || item.id === modelId);
  setText(els.selectedModelInfo, modelDisplayName(modelId));
  if (!modelId) {
    setText(els.selectedModelPath, "-");
    setText(els.selectedModelPathStatus, "-");
    return;
  }
  if (!registry) {
    setText(els.selectedModelPath, t("pathUnknown"));
    setText(els.selectedModelPathStatus, t("pathUnknown"));
    return;
  }
  setText(els.selectedModelPath, registry.path || "-");
  const integrity = registry.integrity || {};
  const integrityText = integrity.complete === true
    ? t("pathComplete")
    : `${t("pathIncomplete")}: ${integrity.reason || "unknown"}`;
  setText(els.selectedModelPathStatus, `${t("pathKnown")} / ${registry.exists ? t("pathExists") : t("pathMissing")} / ${integrityText}`);
}

function renderGpu(gpus, error) {
  if (error) {
    els.gpuList.textContent = error;
    return;
  }
  if (!gpus.length) {
    els.gpuList.textContent = t("noGpu");
    return;
  }
  els.gpuList.innerHTML = "";
  for (const gpu of gpus) {
    const row = document.createElement("div");
    row.className = "gpu-row";
    row.innerHTML = `
      <div><strong>GPU ${gpu.index}</strong><span>${gpu.name}</span></div>
      <div>${gpu.temp_c}C</div>
      <div>${Number(gpu.power_w).toFixed(0)}W / ${Number(gpu.power_limit_w).toFixed(0)}W</div>
      <div>${gpu.util_pct}%</div>
    `;
    els.gpuList.append(row);
  }
}

function renderRuntime() {
  const processes = state.runtime?.processes || [];
  if (!processes.length) {
    els.runtimeList.innerHTML = `<p class="hint">${t("noRuntime")}</p>`;
    return;
  }
  els.runtimeList.innerHTML = "";
  for (const process of processes) {
    const diagnostic = process.diagnostic || {};
    const title = diagnosticField(diagnostic, "title") || diagnostic.code || process.status || "-";
    const detail = diagnosticField(diagnostic, "detail") || "-";
    const nextAction = diagnosticField(diagnostic, "next_action") || "-";
    const recentLog = Array.isArray(diagnostic.recent_log) ? diagnostic.recent_log.slice(-7) : [];
    const severity = diagnostic.severity || (process.running ? "warn" : "muted");
    const hasMetricPoolJob = process.running && process.backend === "akoya_vllm" && Number(state.metrics?.jobs_received) > 0;
    const healthLabel = diagnostic.health_online ? runtimeLabel("online") : runtimeLabel("offline");
    const poolJobLabel = (diagnostic.has_pool_job || hasMetricPoolJob) ? runtimeLabel("yes") : runtimeLabel("no");
    const item = document.createElement("div");
    item.className = `runtime-item ${process.running ? "running" : "stopped"} severity-${severity}`;
    item.innerHTML = `
      <div class="runtime-main">
        <div>
          <strong>${escapeHtml(process.profile_id || "-")}</strong>
          <span>${escapeHtml(process.status || "-")} · pid ${escapeHtml(process.pid || "-")} · ${runtimeLabel("gpu")} ${escapeHtml(process.gpu || "-")}${process.monitor_pid ? ` · ${runtimeLabel("monitor")} pid ${escapeHtml(process.monitor_pid)}` : ""}</span>
        </div>
        <span class="runtime-stage">${escapeHtml(title)}</span>
      </div>
      <div class="runtime-diagnostics">
        <div><span>${runtimeLabel("age")}</span><strong>${formatAge(diagnostic.age_seconds)}</strong></div>
        <div><span>${runtimeLabel("health")}</span><strong>${escapeHtml(healthLabel)}</strong></div>
        <div><span>${runtimeLabel("poolJob")}</span><strong>${escapeHtml(poolJobLabel)}</strong></div>
      </div>
      <p class="runtime-detail">${escapeHtml(detail)}</p>
      <p class="runtime-action">${runtimeLabel("next")}: ${escapeHtml(nextAction)}</p>
      ${diagnostic.recent_error ? `<p class="runtime-error">${runtimeLabel("error")}: ${escapeHtml(diagnostic.recent_error)}</p>` : ""}
      <details class="runtime-log">
        <summary>${runtimeLabel("log")}</summary>
        <pre>${escapeHtml(recentLog.join("\n") || "-")}</pre>
      </details>
      <p class="runtime-path">${runtimeLabel("path")}: ${escapeHtml(process.log_path || "-")}</p>
      ${process.monitor_error ? `<p class="runtime-error">${runtimeLabel("monitor")}: ${escapeHtml(process.monitor_error)}</p>` : ""}
    `;
    els.runtimeList.append(item);
  }
}

function renderEvidence(evidence) {
  state.evidence = evidence || state.evidence;
  const current = evidence || state.evidence || {};
  const delta = current.delta || {};
  const summary = current.summary || {};
  const usage = current.usage || {};
  const shareDelta = (delta.share_results ?? "-") + (delta.share_rejects ? ` / rejected ${delta.share_rejects}` : "");
  const verdictText = state.lang === "en"
    ? (current.verdict_en || current.verdict || t("noEvidence"))
    : (current.verdict_zh || current.verdict || t("noEvidence"));
  els.evidenceVerdict.textContent = verdictText;
  els.evidenceVerdict.className = `badge ${current.share_proven || current.useful ? "good" : current.snapshot_useful ? "warn" : "muted"}`;
  setText(els.evidenceGemms, fmt(delta.request_gemms));
  setText(els.evidenceCapi, fmt(delta.useful_capi_calls));
  setText(els.evidenceLaunches, fmt(delta.completed_launches ?? delta.completed_launches_total));
  setText(els.evidenceShares, shareDelta);
  const kernelText = `${fmt(delta.pearl_kernel_eligible)} / skipped ${fmt(delta.pearl_kernel_skipped)}`;
  setText(els.evidenceKernel, kernelText);
  setText(els.evidenceTokens, usage.total_tokens ? `${usage.total_tokens}` : "-");
  setText(els.evidenceHashrate, summary.useful_hashrate_label || "-");

  const reasons = current.reasons || [];
  els.evidenceReasons.innerHTML = "";
  if (!reasons.length) {
    const li = document.createElement("li");
    li.textContent = t("noWarnings");
    els.evidenceReasons.append(li);
  } else {
    for (const reason of reasons.slice(0, 6)) {
      const li = document.createElement("li");
      const reasonText = state.lang === "en"
        ? (reason.text_en || reason.text || "-")
        : (reason.text || reason.text_en || "-");
      li.textContent = `${reason.code}: ${reasonText}`;
      els.evidenceReasons.append(li);
    }
  }

  const layers = current.layers || summary.layers || [];
  els.layerList.innerHTML = "";
  for (const layer of layers.slice(0, 8)) {
    const row = document.createElement("div");
    row.className = "layer-row";
    row.innerHTML = `
      <span>L${layer.layer_id}</span>
      <strong>${layer.hashrate_label || "-"}</strong>
      <em>${layer.avg_total_ms === null || layer.avg_total_ms === undefined ? "-" : Number(layer.avg_total_ms).toFixed(2) + " ms"}</em>
    `;
    els.layerList.append(row);
  }
}

function renderBackgroundStatus(theme) {
  if (!els.backgroundStatus) return;
  if (theme?.has_background) {
    els.backgroundStatus.textContent = `${t("backgroundReady")}: ${theme.background_name || ""}`;
  } else {
    els.backgroundStatus.textContent = t("backgroundNone");
  }
}

function applyTheme(theme) {
  state.theme = theme || {};
  if (theme?.has_background && theme.background_url) {
    document.body.style.setProperty("--custom-bg", `url("${theme.background_url}")`);
    document.body.classList.add("has-custom-bg");
  } else {
    document.body.style.removeProperty("--custom-bg");
    document.body.classList.remove("has-custom-bg");
  }
  renderBackgroundStatus(theme);
}

function mergeImportSummary(summary) {
  if (!summary) return;
  if (Array.isArray(summary.models) && summary.models.length) {
    state.registryModels = summary.models;
    if (!state.modelDetails.length) {
      state.modelDetails = summary.models.map((model) => ({
        id: model.id,
        path: model.path,
        registry: model,
      }));
    }
  }
  if (Array.isArray(summary.profiles) && summary.profiles.length && !state.profiles.length) {
    state.profiles = summary.profiles;
  }
}

async function refreshImportSummary() {
  try {
    mergeImportSummary(await api("/api/import/summary"));
  } catch (error) {
    els.runtimeMessage.textContent = `${t("requestFailed")}: ${error.message}`;
  }
}

async function refreshStatus() {
  const status = await api("/api/status");
  const metrics = status.metrics || {};
  state.metrics = metrics;
  setHealth(Boolean(status.health?.online), status.health?.error);
  setText(els.apiBase, status.api_base || "-");
  setText(els.updateTime, status.time || "-");
  setText(els.usefulHashrate, metrics.useful_hashrate_label || "-");
  setText(els.poolRegistered, fmt(metrics.pool_registered));
  setText(els.poolStream, fmt(metrics.inference_stream_connected));
  setText(els.jobsReceived, fmt(metrics.jobs_received));
  const shareText = `${fmt(metrics.share_results_total)} / rejected ${fmt(metrics.share_rejects_total)}`;
  setText(els.shareTotals, shareText);
  const kernelText = `${fmt(metrics.pearl_kernel_eligible_total)} eligible / ${fmt(metrics.pearl_kernel_skipped_total)} skipped`;
  setText(els.kernelTotals, kernelText);
  setText(els.miningEnabled, fmt(metrics.worker_mining_enabled));
  state.models = status.models || [];
  state.modelDetails = status.model_details || [];
  state.registryModels = status.model_registry?.models || [];
  state.profiles = status.run_profiles?.profiles || [];
  state.gpus = status.gpu || [];
  state.loadingProfiles = false;
  state.runtime = status.runtime || null;
  if (!state.evidence) state.evidence = status.evidence || null;
  if (!state.registryModels.length || !state.modelDetails.length || !state.profiles.length) {
    await refreshImportSummary();
  }
  renderProfiles();
  renderModelOptions();
  renderRuntime();
  renderEvidence(state.evidence || status.evidence);
  renderGpu(state.gpus, status.gpu_error);
  renderGpuPicker();
}

async function refreshRunProfiles() {
  if (!state.profiles.length) {
    state.loadingProfiles = true;
    renderProfiles();
  }
  try {
    const data = await api("/api/run-profiles");
    state.profiles = data.profiles || [];
  } catch (error) {
    state.profiles = [];
    els.runtimeMessage.textContent = `${t("requestFailed")}: ${error.message}`;
  } finally {
    state.loadingProfiles = false;
    renderProfiles();
  }
}

async function refreshTheme() {
  const theme = await api("/api/theme");
  applyTheme(theme);
}

function addMessage(role, text, meta = "") {
  const empty = els.chatLog.querySelector(".empty-state");
  if (empty) empty.remove();
  const node = document.createElement("article");
  node.className = `message ${role}`;
  const label = role === "user" ? t("roleUser") : t("roleAssistant");
  node.innerHTML = `<header><strong>${label}</strong><span>${meta}</span></header><p></p>`;
  node.querySelector("p").textContent = text;
  els.chatLog.append(node);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

async function sendChat(event) {
  event.preventDefault();
  if (state.busy) return;
  const prompt = els.promptInput.value.trim();
  const model = state.selectedModel || els.modelSelect.value || els.runtimeModel.value;
  if (!prompt) return;
  if (!model) {
    addMessage("assistant", t("noModel"));
    return;
  }
  state.busy = true;
  els.sendBtn.disabled = true;
  addMessage("user", prompt);
  addMessage("assistant", t("thinking"));
  els.promptInput.value = "";
  try {
    const payload = {
      model,
      messages: [{ role: "user", content: prompt }],
      max_tokens: Number(els.maxTokens.value || 256),
      temperature: Number(els.temperature.value || 0.3),
    };
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    els.chatLog.lastElementChild.remove();
    addMessage("assistant", data.text || t("emptyOutput"), data.mode || "");
    renderEvidence(data.evidence);
    await refreshStatus();
  } catch (error) {
    els.chatLog.lastElementChild.remove();
    addMessage("assistant", `${t("requestFailed")}: ${error.message}`);
  } finally {
    state.busy = false;
    els.sendBtn.disabled = false;
  }
}

function basename(path) {
  return String(path || "").split(/[\\/]/).filter(Boolean).pop() || "";
}

function stripModelExtension(name) {
  return String(name || "").replace(/\.(gguf|safetensors|bin|pt|pth|onnx)$/i, "");
}

async function chooseModelPath(kind = "folder") {
  const endpoint = kind === "file" ? "/api/dialog/model-file" : "/api/dialog/model-folder";
  els.importModelStatus.textContent = t("choosing");
  try {
    const data = await api(endpoint, { method: "POST" });
    if (data.cancelled) {
      els.importModelStatus.textContent = t("chooserCancelled");
      return false;
    }
    if (!data.path) throw new Error("empty path");
    els.importModelPath.value = data.path;
    if (!els.importModelId.value.trim()) {
      const name = stripModelExtension(data.name || basename(data.path));
      if (name) els.importModelId.value = name;
    }
    els.importModelStatus.textContent = data.path;
    return true;
  } catch (error) {
    els.importModelStatus.textContent = `${t("chooserFailed")}: ${error.message}`;
    return false;
  }
}

async function chooseProfileJson() {
  els.importProfileStatus.textContent = t("choosing");
  try {
    const data = await api("/api/dialog/profile-json", { method: "POST" });
    if (data.cancelled) {
      els.importProfileStatus.textContent = t("chooserCancelled");
      return false;
    }
    if (!data.content) throw new Error("empty file");
    els.importProfileJson.value = data.content;
    els.importProfileStatus.textContent = data.path || t("imported");
    return true;
  } catch (error) {
    els.importProfileStatus.textContent = `${t("chooserFailed")}: ${error.message}`;
    return false;
  }
}

function profileTemplate(kind) {
  const plain = kind === "plain";
  const useful = kind === "useful";
  const profile = {
    id: useful ? "custom-useful-miner-local" : plain ? "custom-plain-miner-local" : "custom-miner-local",
    label: useful ? "Custom useful-work miner" : plain ? "Custom plain miner" : "Custom miner command",
    label_zh: useful ? "自定义 Useful miner" : plain ? "自定义 Plain miner" : "自定义 Miner 命令",
    kind: useful ? "useful" : plain ? "plain" : "custom",
    backend: "custom",
    cwd: "C:\\path\\to\\miner",
    gpu: "0",
    wallet_address: "",
    worker: "PapiMiner-worker",
    log_dir: "local/run-logs/custom-miner",
    notes: state.lang === "zh" ? "未审计，只保存在 local/；确认来源可信后再运行。" : "Unaudited; stored only in local/. Run only after you trust the source.",
  };
  if (useful) {
    return {
      ...profile,
      command: ".\\miner.exe --model {model} --wallet {wallet_address} --worker {worker} --gpu {gpu}",
      model: "C:\\path\\to\\huggingface-model",
      connect_pool: true,
      pool_routed: false,
    };
  }
  if (plain) {
    return {
      ...profile,
      command: ".\\miner.exe --url {pool_host}:{pool_port} --wallet {wallet_address} --worker {worker} --gpu-list {gpu}",
      pool_host: "pool.example.com",
      pool_port: "443",
    };
  }
  return {
    ...profile,
    command: ".\\miner.exe --wallet {wallet_address} --worker {worker} --gpu {gpu}",
  };
}

function fillProfileTemplate(kind) {
  els.importProfileJson.value = JSON.stringify(profileTemplate(kind), null, 2);
  els.importProfileStatus.textContent = t("templateLoaded");
}

async function importModel() {
  if (!els.importModelPath.value.trim()) {
    const selected = await chooseModelPath("folder");
    if (!selected || !els.importModelPath.value.trim()) return;
  }
  const payload = {
    id: els.importModelId.value.trim(),
    path: els.importModelPath.value.trim(),
  };
  try {
    const data = await api("/api/import/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    els.importModelStatus.textContent = `${t("imported")}: ${data.entry?.id || payload.path}`;
    await refreshStatus();
  } catch (error) {
    els.importModelStatus.textContent = `${t("importFailed")}: ${error.message}`;
  }
}

async function importProfile() {
  try {
    if (!els.importProfileJson.value.trim()) {
      const selected = await chooseProfileJson();
      if (!selected || !els.importProfileJson.value.trim()) return;
    }
    const profile = JSON.parse(els.importProfileJson.value || "{}");
    const data = await api("/api/import/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile }),
    });
    els.importProfileStatus.textContent = `${t("imported")}: ${data.profile?.id || "-"}`;
    await refreshStatus();
  } catch (error) {
    els.importProfileStatus.textContent = `${t("importFailed")}: ${error.message}`;
  }
}

async function startRuntime() {
  const profileId = els.profileSelect.value;
  const selectedGpus = parseGpuSelection(els.runtimeGpu.value.trim());
  const autoTp = state.mode === "useful" && selectedGpus.size > 1 ? String(selectedGpus.size) : "";
  const overrides = {
    gpu: els.runtimeGpu.value.trim(),
    tensor_parallel_size: els.runtimeTensorParallel?.value.trim() || autoTp,
    worker: els.runtimeWorker.value.trim(),
    wallet_address: els.runtimeWallet.value.trim(),
    model: state.selectedModel || els.runtimeModel.value || els.modelSelect.value,
    no_pool: els.runtimeNoPool.checked,
    connect_pool: !els.runtimeNoPool.checked,
    pool_routed: els.poolRouted.checked,
    open_monitor: Boolean(els.openMonitor?.checked),
  };
  try {
    const data = await api("/api/runtime/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, overrides }),
    });
    els.runtimeMessage.textContent = `${t("started")}: pid ${data.process?.pid || "-"}`;
    state.runtime = await api("/api/runtime/status");
    renderRuntime();
  } catch (error) {
    els.runtimeMessage.textContent = error.message;
  }
}

async function stopRuntime() {
  const profileId = els.profileSelect.value;
  try {
    await api("/api/runtime/stop", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId }),
    });
    els.runtimeMessage.textContent = t("stopped");
    state.runtime = await api("/api/runtime/status");
    renderRuntime();
  } catch (error) {
    els.runtimeMessage.textContent = error.message;
  }
}

async function uploadBackground() {
  const file = els.backgroundInput.files?.[0];
  if (!file) return;
  els.backgroundStatus.textContent = t("backgroundUploading");
  try {
    const response = await fetch("/api/theme/background", {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
    applyTheme(data);
    els.backgroundStatus.textContent = t("backgroundUploaded");
  } catch (error) {
    els.backgroundStatus.textContent = `${t("backgroundUploadFailed")}: ${error.message}`;
  } finally {
    els.backgroundInput.value = "";
  }
}

async function resetBackground() {
  const data = await api("/api/theme/reset-background", { method: "POST" });
  applyTheme(data);
}

function bindEvents() {
  for (const button of els.langButtons) {
    button.addEventListener("click", () => setLanguage(button.dataset.lang));
  }
  for (const button of els.viewButtons) {
    button.addEventListener("click", () => setView(button.dataset.view));
  }
  els.admireBackgroundBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    toggleBackgroundFocus();
  });
  document.addEventListener("click", () => {
    if (!state.backgroundFocus) return;
    state.backgroundFocus = false;
    localStorage.setItem("PapiMiner.backgroundFocus", "0");
    applyBackgroundFocus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.backgroundFocus) {
      state.backgroundFocus = false;
      localStorage.setItem("PapiMiner.backgroundFocus", "0");
      applyBackgroundFocus();
    }
  });
  for (const button of els.modeButtons) {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      for (const other of els.modeButtons) other.classList.toggle("active", other === button);
      renderProfiles();
    });
  }
  els.refreshBtn.addEventListener("click", refreshStatus);
  els.profileSelect.addEventListener("change", syncProfileForm);
  els.modelSelect.addEventListener("change", () => setSelectedModel(els.modelSelect.value));
  els.runtimeModel.addEventListener("change", () => setSelectedModel(els.runtimeModel.value));
  els.runtimeGpu.addEventListener("input", () => {
    state.userEditedGpu = true;
    state.gpuOverrides[state.mode] = els.runtimeGpu.value.trim();
    localStorage.setItem(`PapiMiner.gpu.${state.mode}`, state.gpuOverrides[state.mode]);
    renderGpuPicker();
  });
  els.runtimeGpu.addEventListener("change", () => {
    state.userEditedGpu = true;
    state.gpuOverrides[state.mode] = els.runtimeGpu.value.trim();
    localStorage.setItem(`PapiMiner.gpu.${state.mode}`, state.gpuOverrides[state.mode]);
    renderGpuPicker();
  });
  els.gpuPicker?.addEventListener("click", (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target?.closest("button[data-gpu-index]");
    if (!button) return;
    toggleGpuIndex(button.dataset.gpuIndex);
  });
  els.selectTwoGpusBtn?.addEventListener("click", () => {
    setGpuSelection(selectableGpuIndices().slice(0, 2));
  });
  els.selectAllGpusBtn?.addEventListener("click", () => {
    setGpuSelection(selectableGpuIndices());
  });
  els.clearGpusBtn?.addEventListener("click", () => setGpuSelection([]));
  els.browseModelFolderBtn?.addEventListener("click", () => chooseModelPath("folder"));
  els.browseModelFileBtn?.addEventListener("click", () => chooseModelPath("file"));
  els.importModelBtn.addEventListener("click", importModel);
  els.browseProfileJsonBtn?.addEventListener("click", chooseProfileJson);
  els.importProfileBtn.addEventListener("click", importProfile);
  for (const button of els.profileTemplateButtons) {
    button.addEventListener("click", () => fillProfileTemplate(button.dataset.profileTemplate));
  }
  els.startRuntimeBtn.addEventListener("click", startRuntime);
  els.stopRuntimeBtn.addEventListener("click", stopRuntime);
  els.runtimeWalletToggle?.addEventListener("click", toggleWalletVisibility);
  for (const button of els.routeButtons) {
    button.addEventListener("click", () => setUsefulRoute(button.dataset.usefulRoute));
  }
  els.runtimeNoPool.addEventListener("change", syncModeControls);
  els.poolRouted.addEventListener("change", renderRunRevenueHint);
  els.chatForm.addEventListener("submit", sendChat);
  els.promptInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      if (!state.busy) els.chatForm.requestSubmit();
    }
  });
  els.backgroundInput.addEventListener("change", uploadBackground);
  els.resetBackgroundBtn.addEventListener("click", resetBackground);
}

function initProfilePlaceholder() {
  els.importProfileJson.placeholder = JSON.stringify(profileTemplate("plain"), null, 2);
}

async function init() {
  bindEvents();
  initProfilePlaceholder();
  applyI18n();
  await Promise.allSettled([refreshTheme(), refreshRunProfiles(), refreshStatus()]);
  window.setInterval(refreshStatus, 10000);
}

init();
