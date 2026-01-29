/* 로또 번호 생성기 (6/45) */

const STORAGE_KEY = "lotto.history.v1";
const THEME_KEY = "lotto.theme.v1";
const HISTORY_LIMIT = 20;
const GAMES_PER_PICK = 5;

const $ = (sel) => document.querySelector(sel);

const gamesEl = $("#games");
const hintEl = $("#hint");
const historyEl = $("#history");
const generateBtn = $("#generateBtn");
const copyBtn = $("#copyBtn");
const clearHistoryBtn = $("#clearHistoryBtn");
const sortToggle = $("#sortToggle");
const autoCopyToggle = $("#autoCopyToggle");
const toastEl = $("#toast");
const themeBtn = $("#themeBtn");

let currentPick = []; // [{ main:number[], bonus:number }]

function bandOf(n) {
  // 로또 색 구간(관례): 1~10, 11~20, 21~30, 31~40, 41~45
  if (n <= 10) return 1;
  if (n <= 20) return 2;
  if (n <= 30) return 3;
  if (n <= 40) return 4;
  return 5;
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function formatNumbers(nums) {
  return nums.map(pad2).join(", ");
}

function formatGame(game) {
  return `${formatNumbers(game.main)} + 보너스 ${pad2(game.bonus)}`;
}

function formatPick(pick) {
  // 5줄 복사 포맷
  return pick.map((g, i) => `${i + 1}) ${formatGame(g)}`).join("\n");
}

function shuffleInPlace(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function generateGame() {
  const pool = Array.from({ length: 45 }, (_, i) => i + 1);
  shuffleInPlace(pool);
  let main = pool.slice(0, 6);
  const bonus = pool[6]; // main과 중복 없음
  if (sortToggle.checked) main = main.slice().sort((a, b) => a - b);
  return { main, bonus };
}

function generatePick() {
  return Array.from({ length: GAMES_PER_PICK }, () => generateGame());
}

function renderPick(pick) {
  gamesEl.innerHTML = "";

  pick.forEach((game, idx) => {
    const line = document.createElement("div");
    line.className = "gameLine";

    const index = document.createElement("div");
    index.className = "gameIndex";
    index.textContent = String(idx + 1);

    const balls = document.createElement("div");
    balls.className = "gameBalls";

    game.main.forEach((n) => {
      const div = document.createElement("div");
      div.className = "ball";
      div.dataset.band = String(bandOf(n));
      div.textContent = String(n);
      balls.appendChild(div);
    });

    const sep = document.createElement("span");
    sep.className = "gameSep";
    sep.textContent = "+";

    const tag = document.createElement("span");
    tag.className = "bonusTag";
    tag.textContent = "보너스";

    const b = document.createElement("div");
    b.className = "ball ballBonus";
    b.dataset.band = String(bandOf(game.bonus));
    b.textContent = String(game.bonus);

    balls.appendChild(sep);
    balls.appendChild(tag);
    balls.appendChild(b);

    line.appendChild(index);
    line.appendChild(balls);
    gamesEl.appendChild(line);
  });
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  window.clearTimeout(toast.__t);
  toast.__t = window.setTimeout(() => toastEl.classList.remove("show"), 1600);
}

async function copyToClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // ignore
  }
  // fallback
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(ta);
  return ok;
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(items) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, HISTORY_LIMIT)));
}

function renderHistory() {
  const items = loadHistory();
  historyEl.innerHTML = "";

  if (items.length === 0) {
    const li = document.createElement("li");
    li.className = "small";
    li.textContent = "아직 생성한 번호가 없어요.";
    historyEl.appendChild(li);
    return;
  }

  items.forEach((entry) => {
    const li = document.createElement("li");
    li.className = "historyItem";

    const numsWrap = document.createElement("div");
    numsWrap.className = "historyNumsCol";

    const games = Array.isArray(entry.games) ? entry.games : [];
    games.forEach((game, i) => {
      const row = document.createElement("div");
      row.className = "historyLine";

      const label = document.createElement("span");
      label.className = "historyLineLabel";
      label.textContent = `${i + 1}`;

      row.appendChild(label);

      (game.main || []).forEach((n) => {
        const p = document.createElement("span");
        p.className = "pill";
        p.dataset.band = String(bandOf(n));
        p.textContent = String(n);
        row.appendChild(p);
      });

      const sep = document.createElement("span");
      sep.className = "gameSep";
      sep.textContent = "+";
      row.appendChild(sep);

      const b = document.createElement("span");
      b.className = "pill pillBonus";
      b.dataset.band = String(bandOf(game.bonus));
      b.textContent = String(game.bonus);
      row.appendChild(b);

      numsWrap.appendChild(row);
    });

    const actions = document.createElement("div");
    actions.className = "historyActions";

    const useBtn = document.createElement("button");
    useBtn.type = "button";
    useBtn.className = "miniBtn";
    useBtn.textContent = "불러오기";
    useBtn.addEventListener("click", () => {
      currentPick = (entry.games || []).map((g) => ({
        main: (g.main || []).slice(),
        bonus: g.bonus,
      }));
      renderPick(currentPick);
      copyBtn.disabled = false;
      hintEl.textContent = `불러왔어요 (${currentPick.length}게임)`;
      toast("5게임을 불러왔어요");
    });

    const cbtn = document.createElement("button");
    cbtn.type = "button";
    cbtn.className = "miniBtn";
    cbtn.textContent = "복사";
    cbtn.addEventListener("click", async () => {
      const text = formatPick(entry.games || []);
      const ok = await copyToClipboard(text);
      toast(ok ? "복사 완료" : "복사 실패");
    });

    actions.appendChild(useBtn);
    actions.appendChild(cbtn);

    li.appendChild(numsWrap);
    li.appendChild(actions);
    historyEl.appendChild(li);
  });
}

function addToHistory(pick) {
  const items = loadHistory();
  const newEntry = {
    games: pick.map((g) => ({ main: g.main.slice(), bonus: g.bonus })),
    at: Date.now(),
  };
  items.unshift(newEntry);
  saveHistory(items);
  renderHistory();
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
  localStorage.setItem(THEME_KEY, theme);
}

function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
    return;
  }
  // 시스템 선호도
  const prefersLight =
    window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  applyTheme(prefersLight ? "light" : "dark");
}

function init() {
  initTheme();
  renderHistory();

  generateBtn.addEventListener("click", async () => {
    currentPick = generatePick();
    renderPick(currentPick);
    copyBtn.disabled = false;
    addToHistory(currentPick);

    const text = formatPick(currentPick);
    hintEl.textContent = `생성됨: 5게임`;

    if (autoCopyToggle.checked) {
      const ok = await copyToClipboard(text);
      toast(ok ? "생성 + 복사 완료" : "생성 완료 (복사 실패)");
    } else {
      toast("5게임 생성 완료");
    }
  });

  copyBtn.addEventListener("click", async () => {
    if (!currentPick.length) return;
    const ok = await copyToClipboard(formatPick(currentPick));
    toast(ok ? "복사 완료" : "복사 실패");
  });

  clearHistoryBtn.addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEY);
    renderHistory();
    toast("히스토리를 비웠어요");
  });

  themeBtn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    applyTheme(cur === "light" ? "dark" : "light");
    toast("테마 전환");
  });

  // 첫 화면: 기본 안내용 예시 공 표시
  currentPick = [
    { main: [7, 12, 23, 29, 35, 41], bonus: 9 },
    { main: [3, 11, 19, 26, 32, 44], bonus: 15 },
    { main: [1, 8, 16, 24, 33, 45], bonus: 27 },
    { main: [5, 14, 21, 28, 39, 42], bonus: 10 },
    { main: [2, 13, 22, 30, 36, 40], bonus: 6 },
  ];
  renderPick(currentPick);
}

document.addEventListener("DOMContentLoaded", init);

