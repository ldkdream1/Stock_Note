let priceChart = null;
let currentStockInfo = null;
let currentUser = null;
let myWatchlist = []; // [{ stock_code, stock_name, market }]
let isSignUpMode = false;

// Supabase Client 초기화
const SUPABASE_URL = "https://pflegllchnkiixnuidep.supabase.co";
const SUPABASE_KEY = "sb_publishable_5LDfTpkVViNZDFphF8OmTQ_H5mSPpe4";
let supabaseClient = null;

if (window.supabase) {
  supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);
}

document.addEventListener("DOMContentLoaded", () => {
  // 1. API Key 불러오기 및 엔진 상태 갱신
  updateEngineStatus();

  // 2. Supabase Auth 및 관심종목 초기화
  initSupabaseAuth();

  // 3. 검색 및 칩 이벤트
  const tickerInput = document.getElementById("ticker-input");
  const btnAnalyze = document.getElementById("btn-analyze");
  const quickChips = document.querySelectorAll(".quick-chip");
  const autocompleteList = document.getElementById("autocomplete-list");

  btnAnalyze.addEventListener("click", () => {
    const val = tickerInput.value.trim();
    if (val) triggerAnalyze(val);
  });

  tickerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      autocompleteList.classList.add("hidden");
      const val = tickerInput.value.trim();
      if (val) triggerAnalyze(val);
    }
  });

  // 추천 칩 클릭
  quickChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const ticker = chip.getAttribute("data-ticker");
      tickerInput.value = ticker;
      autocompleteList.classList.add("hidden");
      triggerAnalyze(ticker);
    });
  });

  // 자동완성 (디바운스)
  let debounceTimer;
  tickerInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = tickerInput.value.trim();
    if (q.length < 1) {
      autocompleteList.classList.add("hidden");
      return;
    }
    debounceTimer = setTimeout(() => {
      fetchAutocomplete(q);
    }, 250);
  });

  // 외부 클릭 시 자동완성 닫기
  document.addEventListener("click", (e) => {
    if (!tickerInput.contains(e.target) && !autocompleteList.contains(e.target)) {
      autocompleteList.classList.add("hidden");
    }
  });

  // 설정 모달
  setupSettingsModal();

  // 인증 모달 & 관심종목 토글 버튼
  setupAuthModal();
  setupWatchlistToggle();

  // 모바일 전용 탭 스위처 및 스크롤 버튼
  setupMobileInteractions();

  // 최초 로드 시 "삼성전자" 기본 분석 자동 실행
  triggerAnalyze("삼성전자");
});

/* =========================================================
   Supabase Auth & Watchlist (관심종목 클라우드 동기화)
   ========================================================= */

async function initSupabaseAuth() {
  if (!supabaseClient) return;

  // 1. 기존 세션 확인
  const { data: { session } } = await supabaseClient.auth.getSession();
  handleAuthState(session?.user || null);

  // 2. 인증 상태 변화 리스너
  supabaseClient.auth.onAuthStateChange((_event, session) => {
    handleAuthState(session?.user || null);
  });
}

function handleAuthState(user) {
  currentUser = user;
  const btnOpenAuth = document.getElementById("btn-open-auth");
  const userProfile = document.getElementById("user-profile");
  const userEmailDisplay = document.getElementById("user-email-display");
  const watchlistWrapper = document.getElementById("watchlist-wrapper");

  if (currentUser) {
    btnOpenAuth.classList.add("hidden");
    userProfile.classList.remove("hidden");
    userEmailDisplay.textContent = currentUser.email.split("@")[0];
    userEmailDisplay.title = currentUser.email;
    watchlistWrapper.classList.remove("hidden");
    fetchWatchlist();
  } else {
    btnOpenAuth.classList.remove("hidden");
    userProfile.classList.add("hidden");
    watchlistWrapper.classList.add("hidden");
    myWatchlist = [];
    updateFavButtonState();
  }
}

async function fetchWatchlist() {
  if (!supabaseClient || !currentUser) return;
  try {
    const { data, error } = await supabaseClient
      .from("watchlists")
      .select("stock_code, stock_name, market")
      .order("created_at", { ascending: false });

    if (!error && data) {
      myWatchlist = data;
      renderWatchlistChips();
      updateFavButtonState();
    }
  } catch (err) {
    console.error("Watchlist fetch error:", err);
  }
}

function renderWatchlistChips() {
  const container = document.getElementById("watchlist-chips");
  const wrapper = document.getElementById("watchlist-wrapper");

  if (!myWatchlist || myWatchlist.length === 0) {
    container.innerHTML = `<span class="text-[11px] text-slate-500 italic">아직 관심종목이 없습니다. 종목명 옆 ⭐를 눌러보세요!</span>`;
    wrapper.classList.remove("hidden");
    return;
  }

  container.innerHTML = myWatchlist.map(item => `
    <div class="flex-shrink-0 inline-flex items-center space-x-1 pl-2.5 pr-1.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs hover:bg-amber-500/20 transition group">
      <span class="cursor-pointer font-medium" onclick="triggerAnalyze('${item.stock_name}')">${item.stock_name}</span>
      <button class="p-0.5 hover:text-rose-400 text-amber-400/60 transition" onclick="removeWatchlistDirect(event, '${item.stock_code}')" title="삭제">
        <i data-lucide="x" class="w-3 h-3"></i>
      </button>
    </div>
  `).join("");

  wrapper.classList.remove("hidden");
  if (window.lucide) window.lucide.createIcons();
}

function setupWatchlistToggle() {
  const btnToggleFav = document.getElementById("btn-toggle-fav");
  btnToggleFav.addEventListener("click", async () => {
    if (!currentUser) {
      openAuthModal();
      return;
    }
    if (!currentStockInfo || !currentStockInfo.code) return;

    const code = currentStockInfo.code;
    const name = currentStockInfo.stock_name;
    const market = currentStockInfo.market || "KOSPI";

    const isFav = myWatchlist.some(w => w.stock_code === code);

    btnToggleFav.disabled = true;
    try {
      if (isFav) {
        // 관심종목 삭제
        await supabaseClient
          .from("watchlists")
          .delete()
          .match({ user_id: currentUser.id, stock_code: code });
      } else {
        // 관심종목 추가
        await supabaseClient
          .from("watchlists")
          .insert({
            user_id: currentUser.id,
            stock_code: code,
            stock_name: name,
            market: market
          });
      }
      await fetchWatchlist();
    } catch (err) {
      console.error("Toggle favorite error:", err);
    } finally {
      btnToggleFav.disabled = false;
    }
  });
}

async function removeWatchlistDirect(e, code) {
  e.stopPropagation();
  if (!supabaseClient || !currentUser) return;
  try {
    await supabaseClient
      .from("watchlists")
      .delete()
      .match({ user_id: currentUser.id, stock_code: code });
    await fetchWatchlist();
  } catch (err) {
    console.error("Direct remove watchlist error:", err);
  }
}

function updateFavButtonState() {
  const btnToggleFav = document.getElementById("btn-toggle-fav");
  const favIcon = document.getElementById("fav-icon");
  const favText = document.getElementById("fav-text");

  if (!btnToggleFav || !currentStockInfo) return;

  const code = currentStockInfo.code;
  const isFav = myWatchlist.some(w => w.stock_code === code);

  if (isFav) {
    btnToggleFav.className = "ml-1 sm:ml-2 px-2.5 py-1 rounded-full text-xs font-semibold border transition flex items-center space-x-1 bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30";
    favIcon.className = "w-3.5 h-3.5 fill-amber-400 text-amber-400";
    favText.textContent = "관심종목 등록됨";
  } else {
    btnToggleFav.className = "ml-1 sm:ml-2 px-2.5 py-1 rounded-full text-xs font-semibold border transition flex items-center space-x-1 bg-slate-800/80 text-slate-300 border-slate-700 hover:text-amber-300";
    favIcon.className = "w-3.5 h-3.5 text-slate-400";
    favText.textContent = "관심종목 담기";
  }
  if (window.lucide) window.lucide.createIcons();
}

function setupAuthModal() {
  const modal = document.getElementById("auth-modal");
  const btnOpen = document.getElementById("btn-open-auth");
  const btnClose = document.getElementById("btn-close-auth-modal");
  const btnLogout = document.getElementById("btn-logout");
  const authForm = document.getElementById("auth-form");
  const toggleBtn = document.getElementById("btn-toggle-auth-mode");
  const titleEl = document.getElementById("auth-modal-title");
  const submitBtn = document.getElementById("btn-auth-submit");
  const togglePrompt = document.getElementById("auth-toggle-prompt");
  const errorMsg = document.getElementById("auth-error-msg");

  btnOpen.addEventListener("click", () => openAuthModal());
  btnClose.addEventListener("click", () => modal.classList.add("hidden"));

  btnLogout.addEventListener("click", async () => {
    if (supabaseClient) {
      await supabaseClient.auth.signOut();
    }
  });

  toggleBtn.addEventListener("click", () => {
    isSignUpMode = !isSignUpMode;
    errorMsg.classList.add("hidden");
    if (isSignUpMode) {
      titleEl.textContent = "회원가입";
      submitBtn.querySelector("span").textContent = "회원가입 완료";
      togglePrompt.textContent = "이미 계정이 있으신가요?";
      toggleBtn.textContent = "로그인";
    } else {
      titleEl.textContent = "로그인";
      submitBtn.querySelector("span").textContent = "로그인";
      togglePrompt.textContent = "계정이 없으신가요?";
      toggleBtn.textContent = "회원가입";
    }
  });

  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!supabaseClient) return;

    const email = document.getElementById("auth-email").value.trim();
    const password = document.getElementById("auth-password").value.trim();
    submitBtn.disabled = true;
    errorMsg.classList.add("hidden");

    try {
      if (isSignUpMode) {
        // 회원가입
        const { data, error } = await supabaseClient.auth.signUp({ email, password });
        if (error) throw error;
        alert("회원가입이 완료되었습니다! 로그인 상태로 전환됩니다.");
        modal.classList.add("hidden");
      } else {
        // 로그인
        const { data, error } = await supabaseClient.auth.signInWithPassword({ email, password });
        if (error) throw error;
        modal.classList.add("hidden");
      }
    } catch (err) {
      errorMsg.textContent = err.message || "인증에 실패했습니다.";
      errorMsg.classList.remove("hidden");
    } finally {
      submitBtn.disabled = false;
    }
  });
}

function openAuthModal() {
  const modal = document.getElementById("auth-modal");
  const errorMsg = document.getElementById("auth-error-msg");
  errorMsg.classList.add("hidden");
  modal.classList.remove("hidden");
}

/* =========================================================
   App Interactions & Analysis
   ========================================================= */

function setupMobileInteractions() {
  // 1. 모바일 탭 바 전환 (수급 동향 / 종목 뉴스 / 주주 토론방)
  const tabBtns = document.querySelectorAll(".mobile-tab-btn");
  const tabContents = document.querySelectorAll(".mobile-tab-content");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");

      tabBtns.forEach(b => {
        b.className = "mobile-tab-btn flex-1 py-2 text-center rounded-lg text-slate-400 hover:text-white transition";
      });
      btn.className = "mobile-tab-btn flex-1 py-2 text-center rounded-lg bg-indigo-600 text-white font-semibold transition";

      tabContents.forEach(content => {
        if (content.id === targetId) {
          content.classList.remove("hidden");
        } else {
          content.classList.add("hidden");
        }
      });
    });
  });

  // 2. 모바일 Scroll to Top 플로팅 버튼
  const btnScrollTop = document.getElementById("btn-scroll-top");
  if (btnScrollTop) {
    window.addEventListener("scroll", () => {
      if (window.scrollY > 350) {
        btnScrollTop.classList.remove("opacity-0", "pointer-events-none");
        btnScrollTop.classList.add("opacity-100");
      } else {
        btnScrollTop.classList.add("opacity-0", "pointer-events-none");
        btnScrollTop.classList.remove("opacity-100");
      }
    });

    btnScrollTop.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
}

async function updateEngineStatus() {
  const savedKey = localStorage.getItem("GEMINI_API_KEY");
  const engineName = document.getElementById("engine-name");
  let hasKey = Boolean(savedKey && savedKey.trim());
  if (!hasKey) {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        hasKey = Boolean(data.has_gemini_key);
      }
    } catch (e) {}
  }
  if (hasKey) {
    engineName.textContent = "Gemini 2.5 Flash AI";
    engineName.parentElement.classList.remove("text-slate-300");
    engineName.parentElement.classList.add("text-indigo-300");
  } else {
    engineName.textContent = "AI Quant Rule Engine";
    engineName.parentElement.classList.remove("text-indigo-300");
    engineName.parentElement.classList.add("text-slate-300");
  }
}

function setupSettingsModal() {
  const modal = document.getElementById("settings-modal");
  const btnOpen = document.getElementById("btn-open-settings");
  const btnClose = document.getElementById("btn-close-modal");
  const btnSave = document.getElementById("btn-save-key");
  const btnClear = document.getElementById("btn-clear-key");
  const keyInput = document.getElementById("gemini-key-input");

  btnOpen.addEventListener("click", () => {
    keyInput.value = localStorage.getItem("GEMINI_API_KEY") || "";
    modal.classList.remove("hidden");
  });

  btnClose.addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  btnSave.addEventListener("click", () => {
    const val = keyInput.value.trim();
    if (val) {
      localStorage.setItem("GEMINI_API_KEY", val);
    } else {
      localStorage.removeItem("GEMINI_API_KEY");
    }
    updateEngineStatus();
    modal.classList.add("hidden");
  });

  btnClear.addEventListener("click", () => {
    keyInput.value = "";
    localStorage.removeItem("GEMINI_API_KEY");
    updateEngineStatus();
    modal.classList.add("hidden");
  });
}

async function fetchAutocomplete(query) {
  const autocompleteList = document.getElementById("autocomplete-list");
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) return;
    const data = await res.json();
    const candidates = data.candidates || [];

    if (candidates.length === 0) {
      autocompleteList.classList.add("hidden");
      return;
    }

    autocompleteList.innerHTML = candidates.map(c => `
      <div class="px-4 py-2.5 hover:bg-slate-800/80 cursor-pointer flex items-center justify-between text-xs transition" data-code="${c.code}" data-name="${c.name}">
        <div class="flex items-center space-x-2">
          <span class="font-bold text-white text-sm">${c.name}</span>
          <span class="text-slate-400 font-mono">${c.code}</span>
        </div>
        <div class="flex items-center space-x-1.5">
          <span class="text-[11px] text-slate-500">${c.sector || ''}</span>
          <span class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400">${c.market || ''}</span>
        </div>
      </div>
    `).join("");

    autocompleteList.querySelectorAll("div[data-code]").forEach(item => {
      item.addEventListener("click", () => {
        const name = item.getAttribute("data-name");
        document.getElementById("ticker-input").value = name;
        autocompleteList.classList.add("hidden");
        triggerAnalyze(name);
      });
    });

    autocompleteList.classList.remove("hidden");
  } catch (err) {
    console.error("Autocomplete error:", err);
  }
}

async function triggerAnalyze(ticker) {
  const loading = document.getElementById("loading-state");
  const errorState = document.getElementById("error-state");
  const dashboard = document.getElementById("dashboard-content");
  const btnAnalyze = document.getElementById("btn-analyze");

  loading.classList.remove("hidden");
  errorState.classList.add("hidden");
  dashboard.classList.add("hidden");
  btnAnalyze.disabled = true;

  try {
    const apiKey = localStorage.getItem("GEMINI_API_KEY") || null;
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: ticker, gemini_api_key: apiKey })
    });

    const result = await res.json();
    if (!res.ok || !result.success) {
      throw new Error(result.detail || "분석 요청에 실패했습니다.");
    }

    currentStockInfo = result.data.info;
    renderDashboard(result.data, result.ai_report);
    updateFavButtonState();
    dashboard.classList.remove("hidden");
  } catch (err) {
    console.error("Analyze error:", err);
    document.getElementById("error-title").textContent = "분석 실패";
    document.getElementById("error-message").textContent = err.message || "오류가 발생했습니다.";
    errorState.classList.remove("hidden");
  } finally {
    loading.classList.add("hidden");
    btnAnalyze.disabled = false;
  }
}

function renderDashboard(data, report) {
  const info = data.info || {};
  const tech = data.technical || {};
  const candles = data.candles || [];
  const news = data.news || [];
  const discussions = data.discussions || [];

  // 1. Overview Header
  document.getElementById("stock-name").textContent = info.stock_name || "--";
  document.getElementById("stock-code").textContent = info.code || "000000";
  document.getElementById("stock-market").textContent = info.market || "KOSPI";
  document.getElementById("stock-sector").textContent = info.sector || "일반";
  document.getElementById("stock-market-cap").textContent = info.market_cap ? `${info.market_cap}억원` : "--";
  document.getElementById("stock-market-rank").textContent = info.market_cap_rank ? `${info.market_cap_rank}위` : "--";

  const price = info.current_price || 0;
  document.getElementById("stock-price").textContent = price.toLocaleString();

  const diffRate = info.diff_rate || 0.0;
  const priceDiff = info.price_diff || 0;
  const diffWrapper = document.getElementById("price-diff-wrapper");
  const diffEl = document.getElementById("price-diff");
  const rateEl = document.getElementById("diff-rate");

  const sign = priceDiff > 0 ? "+" : "";
  diffEl.textContent = `${sign}${priceDiff.toLocaleString()}원`;
  rateEl.textContent = `(${sign}${diffRate.toFixed(2)}%)`;

  if (priceDiff > 0) {
    diffWrapper.className = "flex items-center space-x-1.5 text-xs sm:text-sm font-semibold text-rose-500";
  } else if (priceDiff < 0) {
    diffWrapper.className = "flex items-center space-x-1.5 text-xs sm:text-sm font-semibold text-blue-500";
  } else {
    diffWrapper.className = "flex items-center space-x-1.5 text-xs sm:text-sm font-semibold text-slate-400";
  }

  // Quick Metrics
  document.getElementById("metric-per").textContent = info.per ? `${info.per}배` : "N/A";
  document.getElementById("metric-pbr").textContent = info.pbr ? `${info.pbr}배` : "N/A";
  document.getElementById("metric-div").textContent = info.dividend_yield ? `${info.dividend_yield}%` : "N/A";
  document.getElementById("metric-foreign").textContent = info.foreigner_rate ? `${info.foreigner_rate}%` : "N/A";
  document.getElementById("metric-high52").textContent = info.high_52w ? `${info.high_52w}원` : "N/A";
  document.getElementById("metric-low52").textContent = info.low_52w ? `${info.low_52w}원` : "N/A";

  // 2. AI Score & Opinion
  const score = report.score || 50;
  document.getElementById("ai-score").textContent = score;
  document.getElementById("ai-engine-tag").textContent = report.engine || "AI Agent";

  // SVG Gauge Animation (Dasharray 263.9 기준)
  const circle = document.getElementById("score-circle");
  const circumference = 263.9;
  const offset = circumference - (score / 100) * circumference;
  circle.style.strokeDashoffset = offset;

  // Opinion Styling
  const opinionBadge = document.getElementById("ai-opinion-badge");
  const opinionKo = document.getElementById("ai-opinion-ko");
  const actionDesc = document.getElementById("ai-action-desc");

  opinionBadge.textContent = report.opinion || "HOLD";
  opinionKo.textContent = report.opinion_ko || "중립";
  actionDesc.textContent = report.action_desc || "";

  if (report.opinion === "STRONG BUY" || report.opinion === "BUY") {
    opinionBadge.className = "px-2.5 sm:px-3.5 py-0.5 sm:py-1 text-xs sm:text-sm font-extrabold rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
    circle.setAttribute("class", "text-emerald-500 transition-all duration-1000");
  } else if (report.opinion === "HOLD") {
    opinionBadge.className = "px-2.5 sm:px-3.5 py-0.5 sm:py-1 text-xs sm:text-sm font-extrabold rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30";
    circle.setAttribute("class", "text-amber-500 transition-all duration-1000");
  } else {
    opinionBadge.className = "px-2.5 sm:px-3.5 py-0.5 sm:py-1 text-xs sm:text-sm font-extrabold rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30";
    circle.setAttribute("class", "text-rose-500 transition-all duration-1000");
  }

  // Target Prices
  document.getElementById("target-price-1").textContent = report.target_price_1 ? `${report.target_price_1.toLocaleString()}원` : "N/A";
  document.getElementById("target-price-2").textContent = report.target_price_2 ? `${report.target_price_2.toLocaleString()}원` : "N/A";
  document.getElementById("stop-loss-price").textContent = report.stop_loss ? `${report.stop_loss.toLocaleString()}원` : "N/A";

  // 4 Pillars Breakdown
  const b = report.scores_breakdown || { technical: 15, valuation: 15, flow: 15, momentum: 15 };
  document.getElementById("score-tech").textContent = `${b.technical}/25`;
  document.getElementById("bar-tech").style.width = `${(b.technical / 25) * 100}%`;

  document.getElementById("score-val").textContent = `${b.valuation}/25`;
  document.getElementById("bar-val").style.width = `${(b.valuation / 25) * 100}%`;

  document.getElementById("score-flow").textContent = `${b.flow}/25`;
  document.getElementById("bar-flow").style.width = `${(b.flow / 25) * 100}%`;

  document.getElementById("score-mom").textContent = `${b.momentum}/25`;
  document.getElementById("bar-mom").style.width = `${(b.momentum / 25) * 100}%`;

  // 3-Bullet Summary
  const summaryList = document.getElementById("ai-summary-list");
  const bullets = report.summary || [];
  summaryList.innerHTML = bullets.map(item => `
    <li class="flex items-start space-x-2">
      <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 flex-shrink-0"></span>
      <span class="leading-relaxed">${item}</span>
    </li>
  `).join("");

  // Strategy
  document.getElementById("ai-strategy-content").textContent = report.strategy || "상세 전략 정보가 없습니다.";

  // 3. Technical Grid
  document.getElementById("tech-rsi").textContent = tech.rsi ? tech.rsi.toFixed(1) : "--";
  document.getElementById("rsi-status-badge").textContent = tech.rsi_status || "중립";
  document.getElementById("tech-ma-align").textContent = tech.ma_alignment || "--";
  document.getElementById("tech-cross-signal").textContent = tech.cross_signal || "특이 크로스 신호 없음";

  document.getElementById("tech-bb-pct").textContent = tech.bollinger_pct_b ? `${tech.bollinger_pct_b.toFixed(1)}%` : "--";
  document.getElementById("tech-bb-upper").textContent = tech.bollinger_upper ? `${tech.bollinger_upper.toLocaleString()}원` : "--";
  document.getElementById("tech-bb-mid").textContent = tech.bollinger_mid ? `${tech.bollinger_mid.toLocaleString()}원` : "--";
  document.getElementById("tech-bb-lower").textContent = tech.bollinger_lower ? `${tech.bollinger_lower.toLocaleString()}원` : "--";

  document.getElementById("tech-vol-ratio").textContent = tech.volume_ratio_5d ? tech.volume_ratio_5d.toFixed(1) : "--";
  document.getElementById("tech-disparity").textContent = tech.disparity_20 ? `${tech.disparity_20.toFixed(1)}%` : "--";

  // 4. SWOT Analysis
  const swot = report.swot || { strengths: [], weaknesses: [], opportunities: [], threats: [] };
  renderSwotList("swot-strengths", swot.strengths);
  renderSwotList("swot-weaknesses", swot.weaknesses);
  renderSwotList("swot-opportunities", swot.opportunities);
  renderSwotList("swot-threats", swot.threats);

  // 5. Deal Trend Table
  const dealBody = document.getElementById("deal-trend-body");
  const trends = info.deal_trend || [];
  if (trends.length > 0) {
    dealBody.innerHTML = trends.map(t => {
      const fBuy = t.foreignerPureBuyQuant || "0";
      const oBuy = t.organPureBuyQuant || "0";
      const pBuy = t.individualPureBuyQuant || "0";
      const dt = t.bizdate ? `${t.bizdate.slice(4,6)}.${t.bizdate.slice(6,8)}` : "--";
      return `
        <tr class="hover:bg-slate-800/40 transition">
          <td class="py-2.5 font-medium text-slate-300">${dt}</td>
          <td class="py-2.5 text-right font-mono font-semibold text-slate-200">${t.closePrice || '--'}원</td>
          <td class="py-2.5 text-right font-mono ${getColorClass(fBuy)}">${fBuy}</td>
          <td class="py-2.5 text-right font-mono ${getColorClass(oBuy)}">${oBuy}</td>
          <td class="py-2.5 text-right font-mono ${getColorClass(pBuy)}">${pBuy}</td>
        </tr>
      `;
    }).join("");
  } else {
    dealBody.innerHTML = `<tr><td colspan="5" class="py-4 text-center text-slate-500">수급 동향 데이터가 없습니다.</td></tr>`;
  }

  // 6. Recent News
  const newsList = document.getElementById("news-list");
  if (news.length > 0) {
    newsList.innerHTML = news.map(n => `
      <a href="${n.url || '#'}" target="_blank" rel="noopener noreferrer" class="block p-3 rounded-xl bg-slate-950/60 hover:bg-slate-800/80 border border-slate-800/80 transition group">
        <h4 class="text-xs font-semibold text-slate-200 group-hover:text-indigo-400 line-clamp-1 transition">${n.title}</h4>
        <div class="flex items-center space-x-2 mt-1.5 text-[10px] text-slate-500">
          <span>${n.source || '증권뉴스'}</span>
          <span>•</span>
          <span>${n.date || ''}</span>
        </div>
      </a>
    `).join("");
  } else {
    newsList.innerHTML = `<p class="text-xs text-slate-500 py-4 text-center">최근 뉴스가 없습니다.</p>`;
  }

  // 7. Community Discussions
  const discList = document.getElementById("discussion-list");
  if (discussions.length > 0) {
    discList.innerHTML = discussions.map(d => {
      const holderBadge = d.is_holder 
        ? `<span class="px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-semibold">주주</span>` 
        : '';
      return `
        <a href="${d.url || '#'}" target="_blank" rel="noopener noreferrer" class="block p-3 rounded-xl bg-slate-950/60 hover:bg-slate-800/80 border border-slate-800/80 transition group">
          <div class="flex items-center justify-between gap-1">
            <h4 class="text-xs font-semibold text-slate-200 group-hover:text-indigo-400 line-clamp-1 transition flex-1">${d.title}</h4>
            ${holderBadge}
          </div>
          ${d.content ? `<p class="text-[11px] text-slate-400 mt-1 line-clamp-1 leading-snug">${d.content}</p>` : ''}
          <div class="flex items-center justify-between mt-1.5 text-[10px] text-slate-500">
            <div class="flex items-center space-x-1.5">
              <span class="text-slate-400 font-medium">${d.author}</span>
              <span>•</span>
              <span>${d.date}</span>
            </div>
            <div class="flex items-center space-x-2">
              <span class="flex items-center space-x-0.5 text-slate-400">
                <i data-lucide="thumbs-up" class="w-3 h-3 text-slate-500"></i>
                <span>${d.recommend_count || 0}</span>
              </span>
              <span class="flex items-center space-x-0.5 text-slate-400">
                <i data-lucide="message-circle" class="w-3 h-3 text-slate-500"></i>
                <span>${d.comment_count || 0}</span>
              </span>
            </div>
          </div>
        </a>
      `;
    }).join("");
  } else {
    discList.innerHTML = `<p class="text-xs text-slate-500 py-4 text-center">최근 주주 토론글이 없습니다.</p>`;
  }

  // 8. Render Chart
  renderChart(candles, tech);

  // Refresh lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderSwotList(elementId, items) {
  const el = document.getElementById(elementId);
  if (!items || items.length === 0) {
    el.innerHTML = "<li>관련 항목 없음</li>";
    return;
  }
  el.innerHTML = items.map(txt => `<li>${txt}</li>`).join("");
}

function getColorClass(valStr) {
  if (typeof valStr !== "string") return "text-slate-300";
  if (valStr.startsWith("+")) return "text-rose-400 font-semibold";
  if (valStr.startsWith("-")) return "text-blue-400 font-semibold";
  return "text-slate-400";
}

function renderChart(candles, tech) {
  const ctx = document.getElementById("priceChart").getContext("2d");
  if (priceChart) {
    priceChart.destroy();
  }

  if (!candles || candles.length === 0) return;

  const labels = candles.map(c => c.date ? c.date.slice(5) : "");
  const closePrices = candles.map(c => c.close);
  const volumes = candles.map(c => c.volume);

  const sma5 = tech.all_sma5 ? tech.all_sma5.slice(-candles.length) : [];
  const sma20 = tech.all_sma20 ? tech.all_sma20.slice(-candles.length) : [];
  const sma60 = tech.all_sma60 ? tech.all_sma60.slice(-candles.length) : [];

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "종가",
          data: closePrices,
          borderColor: "#f8fafc",
          backgroundColor: "rgba(248, 250, 252, 0.05)",
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          fill: true,
          tension: 0.1,
          yAxisID: "y"
        },
        {
          label: "5일선",
          data: sma5,
          borderColor: "#f43f5e",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
          yAxisID: "y"
        },
        {
          label: "20일선",
          data: sma20,
          borderColor: "#f59e0b",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
          yAxisID: "y"
        },
        {
          label: "60일선",
          data: sma60,
          borderColor: "#6366f1",
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.1,
          yAxisID: "y"
        },
        {
          type: "bar",
          label: "거래량",
          data: volumes,
          backgroundColor: "rgba(99, 102, 241, 0.25)",
          hoverBackgroundColor: "rgba(99, 102, 241, 0.5)",
          yAxisID: "y1",
          barPercentage: 0.5
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0f172a",
          titleColor: "#f8fafc",
          bodyColor: "#cbd5e1",
          borderColor: "#334155",
          borderWidth: 1,
          padding: 8,
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || '';
              if (label) label += ': ';
              if (context.parsed.y !== null) {
                label += context.parsed.y.toLocaleString();
                if (label.includes("거래량")) {
                  label += "주";
                } else {
                  label += "원";
                }
              }
              return label;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(51, 65, 85, 0.3)" },
          ticks: { color: "#64748b", font: { size: 10 } }
        },
        y: {
          type: "linear",
          display: true,
          position: "right",
          grid: { color: "rgba(51, 65, 85, 0.3)" },
          ticks: {
            color: "#94a3b8",
            font: { size: 10 },
            callback: function(value) {
              return value.toLocaleString() + "원";
            }
          }
        },
        y1: {
          type: "linear",
          display: false,
          position: "left",
          grid: { drawOnChartArea: false },
          min: 0,
          max: Math.max(...volumes) * 4
        }
      }
    }
  });
}
