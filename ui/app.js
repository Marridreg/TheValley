/* The Valley — front end.
 *
 * Receives a stream of events pushed from the Python worker thread via
 * window.valley.recv(). Nothing here polls and nothing blocks; prose arrives
 * as deltas and is appended to a live block until prose_end closes it.
 */

const $ = (id) => document.getElementById(id);
const narrative = $("narrative");
const scroll = $("scroll");
const input = $("input");
const statusEl = $("status");

let proseBlock = null;      // the block currently being streamed into
let busy = false;
const history = [];         // input history for up/down
let historyIndex = -1;

/* ── rendering ── */

function append(text, cls) {
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = text;
  narrative.appendChild(div);
  stick();
  return div;
}

function stick() {
  // Only auto-scroll if the player is already near the bottom, so scrolling
  // back to reread isn't yanked away mid-sentence.
  const nearBottom = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 160;
  if (nearBottom) scroll.scrollTop = scroll.scrollHeight;
}

function setStatus(text) {
  statusEl.textContent = text || "";
  statusEl.className = text ? "thinking" : "";
}

function bar(cls, value) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0)) * 100;
  return `<span class="bar ${cls}"><i style="width:${pct}%"></i></span>`;
}

function renderHud(h) {
  const cells = [
    `<span class="cell"><span class="lab">hp</span>${bar("b-hp", h.hp)}<span class="val">${fmt(h.hp)}</span></span>`,
    `<span class="cell"><span class="lab">sta</span>${bar("b-sta", h.stamina)}<span class="val">${fmt(h.stamina)}</span></span>`,
    `<span class="cell"><span class="lab">mold</span>${bar("b-mold", h.mold)}<span class="val">${fmt(h.mold)}</span></span>`,
    cell("weapon", h.ammo ? `${h.weapon} (${h.ammo})` : h.weapon),
    cell("lei", h.lei),
    cell("at", h.location),
    cell("", h.time),
    cell("", h.weather),
    cell("days", h.days_to_ceremony),
    `<span class="cell"><span class="lab">seen</span>${bar("b-eye", h.attention_dimitrescu)}${bar("b-eye", h.attention_village)}</span>`,
    cell("lycan", fmt(h.threat_lycan)),
  ];
  if (h.companion) cells.push(cell("with", h.companion));
  if (h.key_items && h.key_items.length) cells.push(cell("carrying", h.key_items.join(", ")));
  if (h.active_quest) cells.push(cell("→", h.active_quest));
  $("hud").innerHTML = cells.filter(Boolean).join("");
}

function cell(label, value) {
  if (value === null || value === undefined || value === "") return "";
  const lab = label ? `<span class="lab">${esc(label)}</span> ` : "";
  return `<span class="cell">${lab}<span class="val">${esc(String(value))}</span></span>`;
}

function fmt(n) {
  const v = Number(n);
  return Number.isFinite(v) ? v.toFixed(2) : "?";
}

function esc(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function renderPortraits(list) {
  const panel = $("portraits");
  panel.innerHTML = "";
  (list || []).forEach((p) => {
    const card = document.createElement("div");
    card.className = "card";

    if (p.src) {
      const img = document.createElement("img");
      // Portrait paths are relative to the project root; this page lives in ui/.
      img.src = "../" + p.src;
      img.alt = p.npc;
      img.onerror = () => img.replaceWith(placeholder());
      card.appendChild(img);
    } else {
      card.appendChild(placeholder());
    }

    const who = document.createElement("div");
    who.className = "who";
    who.textContent = p.npc.replace(/_/g, " ").toUpperCase();
    card.appendChild(who);

    if (p.mood) {
      const mood = document.createElement("div");
      mood.className = "mood";
      mood.textContent = p.mood.replace(/_/g, " ");
      card.appendChild(mood);
    }
    panel.appendChild(card);
  });
}

function placeholder() {
  const d = document.createElement("div");
  d.className = "noart";
  d.textContent = "?";
  return d;
}

/* ── event intake ── */

window.valley = {
  recv(e) {
    switch (e.type) {
      case "status":
        setStatus(e.text);
        break;

      case "prose_start":
        setStatus("");
        proseBlock = append("", "prose");
        break;

      case "delta":
        if (!proseBlock) proseBlock = append("", "prose");
        proseBlock.textContent += e.text;
        stick();
        break;

      case "prose_end":
        proseBlock = null;
        break;

      case "fragment":
        append(e.text, "fragment");
        break;

      case "discovery":
        append(e.text.replace(/_/g, " "), "discovery");
        break;

      case "system":
        append(e.text, "system");
        break;

      case "error":
        setStatus("");
        proseBlock = null;
        append(e.text, "error");
        break;

      case "debug":
        if (window.__dev) append(e.text, "debug");
        break;

      case "hud":
        renderHud(e.hud);
        break;

      case "portraits":
        renderPortraits(e.portraits);
        break;

      case "usage":
        if (window.__dev) append(`[${e.role}] ${e.text}`, "debug");
        break;

      case "briefing":
        window.__briefing = e.packet;
        break;

      case "meta":
        if (e.preset) window.__preset = e.preset;
        refreshMeta();
        break;

      case "done":
        setStatus("");
        proseBlock = null;
        unlock();
        window.__turn = (window.__turn || 0) + (e.elapsed ? 1 : 0);
        if (e.elapsed) window.__elapsed = e.elapsed;
        refreshMeta();
        break;
    }
  },
};

function refreshMeta() {
  const bits = [];
  if (window.__preset) bits.push(window.__preset);
  if (window.__turn) bits.push(`turn ${window.__turn}`);
  if (window.__elapsed) bits.push(`${window.__elapsed}s`);
  $("meta").textContent = bits.join("   ");
}

/* ── input ── */

function lock() {
  busy = true;
  input.disabled = true;
  input.placeholder = "";
}

function unlock() {
  busy = false;
  input.disabled = false;
  input.placeholder = "what do you do?";
  input.focus();
}

input.addEventListener("keydown", async (ev) => {
  if (ev.key === "Enter" && !busy) {
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    history.push(text);
    historyIndex = history.length;

    if (!text.startsWith("/")) append(text, "action");
    lock();
    try {
      await window.pywebview.api.submit(text);
    } catch (err) {
      append(String(err), "error");
      unlock();
    }
    return;
  }

  if (ev.key === "ArrowUp" && history.length) {
    ev.preventDefault();
    historyIndex = Math.max(0, historyIndex - 1);
    input.value = history[historyIndex] || "";
  } else if (ev.key === "ArrowDown" && history.length) {
    ev.preventDefault();
    historyIndex = Math.min(history.length, historyIndex + 1);
    input.value = history[historyIndex] || "";
  }
});

/* ── overlays and hotkeys ── */

const PANELS = {
  F1: ["STATUS", "/status"],
  F2: ["INVENTORY", "/inventory"],
  F3: ["JOURNAL", "/journal"],
  F4: ["PRESETS", "/preset"],
};

document.addEventListener("keydown", async (ev) => {
  if (ev.key === "Escape") {
    $("overlay").classList.add("hidden");
    input.focus();
    return;
  }

  if (ev.key === "F5") {
    ev.preventDefault();
    showOverlay(
      "GM BRIEFING (raw)",
      window.__briefing
        ? JSON.stringify(window.__briefing, null, 2)
        : "no briefing yet — take a turn first."
    );
    return;
  }

  if (ev.key === "F9") {
    ev.preventDefault();
    const res = JSON.parse(await window.pywebview.api.quicksave());
    append(res.text, "system");
    return;
  }

  const panel = PANELS[ev.key];
  if (panel && !busy) {
    ev.preventDefault();
    // Route through the same command layer the player types, so a panel can
    // never drift out of sync with its slash command.
    const before = narrative.children.length;
    await window.pywebview.api.submit(panel[1]);
    setTimeout(() => {
      const last = narrative.children[narrative.children.length - 1];
      if (narrative.children.length > before && last) {
        showOverlay(panel[0], last.textContent);
        last.remove();
      }
    }, 90);
  }
});

function showOverlay(title, body) {
  $("overlay-title").textContent = title;
  $("overlay-body").textContent = body;
  $("overlay").classList.remove("hidden");
}

/* ── boot ── */

window.addEventListener("pywebviewready", async () => {
  const info = JSON.parse(await window.pywebview.api.boot());
  window.__dev = info.dev_mode;
  window.__preset = info.preset;
  window.__turn = info.turn;
  refreshMeta();

  append(info.banner, "system");
  (info.warnings || []).forEach((w) => append("! " + w, "system"));

  (info.history || []).forEach((m) =>
    append(m.content, m.role === "user" ? "action" : "prose")
  );

  if (!info.history.length && info.opening) {
    append(info.opening, "prose");
  }

  append("─".repeat(52) + "\n/help for commands. F1-F5 for panels.", "system");
  unlock();
});
