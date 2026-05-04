// BookStack RAG — vanilla SPA for the v0.4.0 / Stage 3 release.
//
// Communicates with the add-on's REST API via fetch() with relative URLs so
// the same code works under HA Ingress (where the path prefix changes).
// Streams via fetch + ReadableStream; the SSE format matches what
// app/api.py emits (event: hit / event: delta / event: done).

(() => {
  "use strict";

  // ---- DOM refs ---------------------------------------------------------

  const $ = (sel) => document.querySelector(sel);
  const sidebar = $("#sidebar");
  const conversationListEl = $("#conversation-list");
  const conversationEl = $("#conversation");
  const emptyStateEl = $("#empty-state");
  const composerEl = $("#composer");
  const inputEl = $("#input");
  const sendBtn = $("#btn-send");
  const newChatBtn = $("#btn-new-chat");
  const toggleSidebarBtn = $("#btn-toggle-sidebar");
  const closeSidebarBtn = $("#btn-close-sidebar");
  const activeIdEl = $("#active-conversation");
  const statusLlmEl = $("#status-llm");
  const statusIndexEl = $("#status-index");

  // ---- State ------------------------------------------------------------

  const state = {
    activeConversationId: null,
    streaming: false,
    llmConfigured: false,
    composerLocked: false,
  };

  let statusPollTimer = null;
  const STATUS_POLL_INTERVAL_MS = 1500;

  // ---- Event wiring -----------------------------------------------------

  composerEl.addEventListener("submit", (event) => {
    event.preventDefault();
    sendCurrentInput();
  });

  inputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendCurrentInput();
    }
  });

  inputEl.addEventListener("input", autosizeTextarea);

  newChatBtn.addEventListener("click", () => {
    setActiveConversation(null);
    clearConversation();
    inputEl.focus();
    closeSidebar();
  });

  toggleSidebarBtn.addEventListener("click", openSidebar);
  closeSidebarBtn.addEventListener("click", closeSidebar);

  // ---- Boot -------------------------------------------------------------

  Promise.all([refreshStatus(), refreshConversationList()])
    .catch((err) => console.error("boot failed", err));

  // ---- Status -----------------------------------------------------------

  async function refreshStatus() {
    if (statusPollTimer) {
      clearTimeout(statusPollTimer);
      statusPollTimer = null;
    }
    let body = null;
    let fetchError = null;
    try {
      const res = await fetch("api/status");
      if (!res.ok) throw new Error("HTTP " + res.status);
      body = await res.json();
    } catch (err) {
      fetchError = err;
    }

    if (fetchError) {
      // Most likely the API is still binding the port — keep polling.
      statusLlmEl.className = "status-pill is-warn";
      statusLlmEl.textContent = "Verbinde …";
      statusIndexEl.className = "status-pill is-warn";
      statusIndexEl.textContent = "Add-on startet …";
      applyComposerLock(true, "Add-on startet, bitte warten …");
      statusPollTimer = setTimeout(refreshStatus, STATUS_POLL_INTERVAL_MS);
      return;
    }

    state.llmConfigured = !!body.llm_configured;

    const llmCls = body.llm_configured ? "is-ok" : "is-warn";
    statusLlmEl.className = `status-pill ${llmCls}`;
    statusLlmEl.textContent = body.llm_configured ? "LLM aktiv" : "LLM aus";

    if (body.status === "initializing") {
      statusIndexEl.className = "status-pill is-warn";
      statusIndexEl.textContent = phaseLabel(body.phase, body.indexed);
      // We can serve queries against a partially-populated index once the
      // embedder is loaded and the collection exists, i.e. from the
      // "indexing" phase onwards. Earlier phases must lock the composer.
      const earlyPhase = body.phase === "starting"
        || body.phase === "loading_embedder"
        || body.phase === "creating_collection";
      applyComposerLock(earlyPhase, phasePlaceholder(body.phase));
      statusPollTimer = setTimeout(refreshStatus, STATUS_POLL_INTERVAL_MS);
      return;
    }

    if (body.status === "error") {
      statusIndexEl.className = "status-pill is-error";
      statusIndexEl.textContent = "Init fehlgeschlagen";
      applyComposerLock(true, "Initialisierung fehlgeschlagen — siehe Add-on-Log");
      // Keep polling at a slower cadence in case the user fixes it
      statusPollTimer = setTimeout(refreshStatus, STATUS_POLL_INTERVAL_MS * 4);
      return;
    }

    // status == "ok" or "no_export_dir" — fully initialised
    const indexCls = body.indexed > 0 ? "is-ok" : "is-warn";
    statusIndexEl.className = `status-pill ${indexCls}`;
    statusIndexEl.textContent = `${body.indexed} indiziert`;
    applyComposerLock(false, "Frage eingeben — Enter zum Senden, Shift+Enter für Zeilenumbruch");
  }

  function phaseLabel(phase, indexed) {
    switch (phase) {
      case "starting": return "Startet …";
      case "loading_embedder": return "Lädt Modell …";
      case "creating_collection": return "Bereitet Index vor …";
      case "indexing": return `Indiziert (${indexed}) …`;
      default: return phase || "Initialisiert …";
    }
  }

  function phasePlaceholder(phase) {
    switch (phase) {
      case "starting": return "Add-on initialisiert, bitte warten …";
      case "loading_embedder": return "Lädt Embedding-Modell, bitte warten …";
      case "creating_collection": return "Bereitet Index vor, bitte warten …";
      case "indexing": return "Frage eingeben — Index wird im Hintergrund aufgebaut";
      default: return "Initialisiert, bitte warten …";
    }
  }

  function applyComposerLock(locked, placeholder) {
    state.composerLocked = locked;
    inputEl.placeholder = placeholder;
    if (state.streaming) return; // setStreaming will reset disabled state when done
    sendBtn.disabled = locked;
    inputEl.disabled = locked;
  }

  // ---- Conversation list -----------------------------------------------

  async function refreshConversationList() {
    try {
      const res = await fetch("api/conversations");
      if (!res.ok) throw new Error("status " + res.status);
      const items = await res.json();
      renderConversationList(items);
    } catch (err) {
      conversationListEl.innerHTML = `<li class="error-banner">Liste konnte nicht geladen werden: ${escapeHtml(err.message || String(err))}</li>`;
    }
  }

  function renderConversationList(items) {
    conversationListEl.innerHTML = "";
    if (!items.length) {
      const li = document.createElement("li");
      li.className = "conversation-list-item";
      li.innerHTML = `<span class="conversation-list-item-meta">Noch keine Chats</span>`;
      conversationListEl.appendChild(li);
      return;
    }
    for (const item of items) {
      const li = document.createElement("li");
      li.className = "conversation-list-item";
      if (item.id === state.activeConversationId) li.classList.add("active");
      li.dataset.id = item.id;

      const row = document.createElement("div");
      row.className = "conversation-list-item-row";

      const title = document.createElement("span");
      title.className = "conversation-list-item-title";
      title.textContent = item.title_preview || "(leerer Chat)";
      title.addEventListener("click", () => loadConversation(item.id));

      const del = document.createElement("button");
      del.className = "btn btn-delete";
      del.type = "button";
      del.textContent = "×";
      del.title = "Chat löschen";
      del.addEventListener("click", (event) => {
        event.stopPropagation();
        deleteConversation(item.id);
      });

      row.appendChild(title);
      row.appendChild(del);
      li.appendChild(row);

      const meta = document.createElement("span");
      meta.className = "conversation-list-item-meta";
      meta.textContent = `${item.message_count} Nachrichten · ${formatRelativeDate(item.updated_at)}`;
      li.appendChild(meta);

      li.addEventListener("click", () => loadConversation(item.id));
      conversationListEl.appendChild(li);
    }
  }

  async function loadConversation(id) {
    if (state.streaming) return;
    try {
      const res = await fetch(`api/conversations/${encodeURIComponent(id)}`);
      if (!res.ok) throw new Error("status " + res.status);
      const detail = await res.json();
      setActiveConversation(detail.id);
      clearConversation();
      for (const msg of detail.messages) {
        renderMessage(msg.role, msg.content);
      }
      scrollToBottom();
      closeSidebar();
      refreshConversationList();
    } catch (err) {
      showError("Chat konnte nicht geladen werden: " + (err.message || err));
    }
  }

  async function deleteConversation(id) {
    if (!confirm("Diesen Chat löschen?")) return;
    try {
      const res = await fetch(`api/conversations/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) throw new Error("status " + res.status);
      if (id === state.activeConversationId) {
        setActiveConversation(null);
        clearConversation();
      }
      refreshConversationList();
    } catch (err) {
      showError("Chat konnte nicht gelöscht werden: " + (err.message || err));
    }
  }

  function setActiveConversation(id) {
    state.activeConversationId = id;
    activeIdEl.textContent = id ? id.slice(0, 8) : "";
    Array.from(conversationListEl.querySelectorAll(".conversation-list-item")).forEach((el) => {
      el.classList.toggle("active", el.dataset.id === id);
    });
  }

  function clearConversation() {
    conversationEl.innerHTML = "";
    conversationEl.appendChild(emptyStateEl);
  }

  // ---- Sending a query --------------------------------------------------

  async function sendCurrentInput() {
    const text = inputEl.value.trim();
    if (!text || state.streaming || state.composerLocked) return;
    if (emptyStateEl.parentElement === conversationEl) {
      conversationEl.removeChild(emptyStateEl);
    }
    inputEl.value = "";
    autosizeTextarea();
    renderMessage("user", text);
    scrollToBottom();
    setStreaming(true);
    try {
      if (state.llmConfigured) {
        await sendStreaming(text);
      } else {
        await sendRetrievalOnly(text);
      }
    } catch (err) {
      showError("Anfrage fehlgeschlagen: " + (err.message || err));
    } finally {
      setStreaming(false);
      refreshConversationList();
      refreshStatus();
    }
  }

  async function sendStreaming(text) {
    const body = {
      text,
      stream: true,
    };
    if (state.activeConversationId) body.conversation_id = state.activeConversationId;

    const response = await fetch("api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }

    const messageEl = renderMessage("assistant", "");
    const bubbleEl = messageEl.querySelector(".message-bubble");
    const hitsEl = messageEl.querySelector(".hits");
    bubbleEl.classList.add("streaming-cursor");

    const hits = [];
    let answer = "";

    await consumeSse(response.body, (event, payload) => {
      if (event === "hit") {
        hits.push(payload);
        if (hitsEl) renderHits(hitsEl, hits);
      } else if (event === "delta") {
        answer += payload.content || "";
        bubbleEl.innerHTML = renderMarkdown(answer);
        scrollToBottom();
      } else if (event === "done") {
        if (payload.conversation_id) setActiveConversation(payload.conversation_id);
      } else if (event === "error") {
        throw new Error(payload.detail || "stream error");
      }
    });

    bubbleEl.classList.remove("streaming-cursor");
    if (!answer) {
      bubbleEl.innerHTML = "<em>Keine Antwort erhalten.</em>";
    }
  }

  async function sendRetrievalOnly(text) {
    const body = { text };
    const response = await fetch("api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`HTTP ${response.status}: ${detail}`);
    }
    const data = await response.json();
    const messageEl = renderMessage("assistant", "");
    const bubbleEl = messageEl.querySelector(".message-bubble");
    bubbleEl.innerHTML = "<em>LLM nicht konfiguriert — hier sind die passendsten Doku-Stellen:</em>";
    const hitsEl = messageEl.querySelector(".hits");
    if (hitsEl) renderHits(hitsEl, data.hits || []);
  }

  async function consumeSse(stream, onEvent) {
    const reader = stream.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let blockEnd;
      while ((blockEnd = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, blockEnd);
        buffer = buffer.slice(blockEnd + 2);
        processSseBlock(block, onEvent);
      }
    }
    if (buffer.trim()) processSseBlock(buffer, onEvent);
  }

  function processSseBlock(block, onEvent) {
    let event = "message";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7).trim();
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (!data) return;
    try {
      onEvent(event, JSON.parse(data));
    } catch (err) {
      console.warn("malformed SSE block, skipping", err, data);
    }
  }

  // ---- Rendering --------------------------------------------------------

  function renderMessage(role, content) {
    const wrap = document.createElement("div");
    wrap.className = `message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    if (role === "user") {
      bubble.textContent = content;
    } else {
      bubble.innerHTML = content ? renderMarkdown(content) : "";
    }
    wrap.appendChild(bubble);

    if (role === "assistant") {
      const hitsEl = document.createElement("div");
      hitsEl.className = "hits";
      hitsEl.style.display = "none";
      wrap.appendChild(hitsEl);
    }

    conversationEl.appendChild(wrap);
    return wrap;
  }

  function renderHits(container, hits) {
    if (!hits.length) {
      container.style.display = "none";
      return;
    }
    container.style.display = "";
    const list = hits
      .map((hit) => {
        const title = escapeHtml(hit.title || "(ohne Titel)");
        const score = (typeof hit.score === "number") ? hit.score.toFixed(2) : "";
        const preview = escapeHtml((hit.content_preview || "").slice(0, 220));
        return `<li>
          <div><span class="hit-title">${title}</span><span class="hit-score">Score ${score}</span></div>
          <div class="hit-preview">${preview}</div>
        </li>`;
      })
      .join("");
    container.innerHTML =
      `<button type="button" class="hits-toggle">${hits.length} Quellen</button>` +
      `<ul class="hits-list">${list}</ul>`;
    const toggle = container.querySelector(".hits-toggle");
    const ul = container.querySelector(".hits-list");
    toggle.addEventListener("click", () => {
      ul.style.display = ul.style.display === "none" ? "" : "none";
    });
  }

  function showError(message) {
    const banner = document.createElement("div");
    banner.className = "error-banner";
    banner.textContent = message;
    conversationEl.appendChild(banner);
    scrollToBottom();
  }

  function setStreaming(on) {
    state.streaming = on;
    const blocked = on || state.composerLocked;
    sendBtn.disabled = blocked;
    inputEl.disabled = blocked;
    sendBtn.textContent = on ? "…" : "Senden";
  }

  function autosizeTextarea() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
  }

  function scrollToBottom() {
    conversationEl.scrollTop = conversationEl.scrollHeight;
  }

  function openSidebar() { sidebar.classList.add("is-open"); }
  function closeSidebar() { sidebar.classList.remove("is-open"); }

  function formatRelativeDate(iso) {
    if (!iso) return "";
    const then = new Date(iso);
    const now = new Date();
    const diffSec = Math.floor((now - then) / 1000);
    if (diffSec < 60) return "vor wenigen Sekunden";
    if (diffSec < 3600) return `vor ${Math.floor(diffSec / 60)} Min`;
    if (diffSec < 86400) return `vor ${Math.floor(diffSec / 3600)} Std`;
    if (diffSec < 86400 * 7) return `vor ${Math.floor(diffSec / 86400)} Tagen`;
    return then.toLocaleDateString("de-DE");
  }

  // ---- Markdown rendering ----------------------------------------------
  //
  // Tiny pure-JS Markdown renderer. Covers what LLM answers actually use
  // (paragraphs, headers, lists, code spans, fenced code, links, bold/italic)
  // with HTML-escape-first to keep us safe from injected <script> in the
  // model output. Not full CommonMark — full compliance can come later if
  // we end up vendoring marked.js.

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function safeHref(url) {
    if (/^https?:\/\//i.test(url)) return url;
    if (/^\//.test(url)) return url;
    if (/^\.\.?\//.test(url)) return url;
    return "#";
  }

  function renderInline(text) {
    // text is already HTML-escaped at this point
    let out = text;
    // links: [text](url)
    out = out.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (_, t, u) => {
      const href = escapeHtml(safeHref(u));
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${t}</a>`;
    });
    // inline code: `code`
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
    // bold: **text**
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    // italic: *text* (avoid eating ** by requiring no * neighbours)
    out = out.replace(/(^|[^*])\*([^*\n]+)\*([^*]|$)/g, "$1<em>$2</em>$3");
    return out;
  }

  function renderMarkdown(rawText) {
    if (!rawText) return "";
    const escaped = escapeHtml(rawText);
    const lines = escaped.split("\n");
    const out = [];
    let listOpen = false;
    let codeOpen = false;
    let codeBuffer = [];
    let paraBuffer = [];

    function flushPara() {
      if (paraBuffer.length) {
        out.push("<p>" + renderInline(paraBuffer.join(" ")) + "</p>");
        paraBuffer = [];
      }
    }
    function flushList() {
      if (listOpen) { out.push("</ul>"); listOpen = false; }
    }

    for (const line of lines) {
      if (codeOpen) {
        if (/^```\s*$/.test(line)) {
          out.push("<pre><code>" + codeBuffer.join("\n") + "</code></pre>");
          codeBuffer = [];
          codeOpen = false;
        } else {
          codeBuffer.push(line);
        }
        continue;
      }
      if (/^```/.test(line)) {
        flushPara(); flushList();
        codeOpen = true;
        continue;
      }
      let m;
      if ((m = line.match(/^### (.+)$/))) {
        flushPara(); flushList();
        out.push("<h3>" + renderInline(m[1]) + "</h3>");
        continue;
      }
      if ((m = line.match(/^## (.+)$/))) {
        flushPara(); flushList();
        out.push("<h2>" + renderInline(m[1]) + "</h2>");
        continue;
      }
      if ((m = line.match(/^# (.+)$/))) {
        flushPara(); flushList();
        out.push("<h1>" + renderInline(m[1]) + "</h1>");
        continue;
      }
      if ((m = line.match(/^[-*] (.+)$/))) {
        flushPara();
        if (!listOpen) { out.push("<ul>"); listOpen = true; }
        out.push("<li>" + renderInline(m[1]) + "</li>");
        continue;
      }
      if (line.trim() === "") {
        flushPara(); flushList();
        continue;
      }
      paraBuffer.push(line);
    }
    if (codeOpen && codeBuffer.length) {
      out.push("<pre><code>" + codeBuffer.join("\n") + "</code></pre>");
    }
    flushPara(); flushList();
    return out.join("\n");
  }

})();
