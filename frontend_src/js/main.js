import "bootstrap";
import "./color-modes";

const monitorRoot = document.getElementById("web-display");

if (monitorRoot) {
  const stage = monitorRoot.querySelector(".web-display-stage");
  const accessError = monitorRoot.querySelector(".web-display-access-error");
  const queue = [];
  const queuedIds = new Set();
  let cursor = "";
  let settings = {
    display_mode: "chat",
    display_duration_sec: 8,
    scroll_speed_px: 3,
    overlay_font_size: 24,
    overlay_theme: "default",
  };
  let rendering = false;
  let failures = 0;
  let renderTimer = null;

  function appendFormattedText(container, text) {
    const pattern = /(~~[^~\n]+~~|\*[^*\n]+\*|_[^_\n]+_|`[^`\n]+`)/g;
    let offset = 0;
    for (const match of String(text || "").matchAll(pattern)) {
      container.append(document.createTextNode(text.slice(offset, match.index)));
      const token = match[0];
      let element;
      let content;
      if (token.startsWith("~~")) {
        element = document.createElement("s");
        content = token.slice(2, -2);
      } else if (token.startsWith("*")) {
        element = document.createElement("strong");
        content = token.slice(1, -1);
      } else if (token.startsWith("_")) {
        element = document.createElement("em");
        content = token.slice(1, -1);
      } else {
        element = document.createElement("code");
        content = token.slice(1, -1);
      }
      element.textContent = content;
      container.append(element);
      offset = match.index + token.length;
    }
    container.append(document.createTextNode(String(text || "").slice(offset)));
  }

  function messageElement(message, ticker = false) {
    const element = document.createElement("article");
    element.className = ticker ? "web-display-ticker" : "web-display-message";
    element.dataset.messageId = message.id;

    const name = document.createElement("div");
    name.className = "web-display-name";
    name.textContent = message.display_name || "Anonymous";
    element.append(name);

    if (message.content) {
      const content = document.createElement("div");
      content.className = "web-display-content";
      appendFormattedText(content, message.content);
      element.append(content);
    }

    if (message.media_url) {
      const image = document.createElement("img");
      image.className = "web-display-media";
      image.src = message.media_url;
      image.alt = message.sticker_emoji || "Nachrichtenmedium";
      element.append(image);
    } else if (message.media_type === "sticker" && message.sticker_emoji) {
      const emoji = document.createElement("div");
      emoji.className = "web-display-sticker";
      emoji.textContent = message.sticker_emoji;
      element.append(emoji);
    }
    return element;
  }

  function safeColor(value, fallback) {
    return /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;
  }

  function applyTheme(theme) {
    const chat = theme?.chat || {};
    const chatBackground = chat.background || {};
    const styles = chat.styles || {};
    const ticker = theme?.ticker || {};
    const tickerBackground = ticker.background || {};
    const root = monitorRoot.style;
    root.setProperty("--web-display-canvas", safeColor(theme?.canvas?.background_color, "#0f172a"));
    root.setProperty("--web-display-accent", safeColor(theme?.canvas?.background_accent, "#1e3a5f"));
    root.setProperty("--web-display-bubble", safeColor(chatBackground.color, "#f8fafc"));
    root.setProperty("--web-display-border", safeColor(chatBackground.border_color, "#38bdf8"));
    root.setProperty("--web-display-name", safeColor(styles.name?.color, "#5b21b6"));
    root.setProperty("--web-display-text", safeColor(styles.message?.color, "#111827"));
    root.setProperty("--web-display-ticker", safeColor(tickerBackground.color, "#172033"));
    root.setProperty("--web-display-ticker-border", safeColor(tickerBackground.border_color, "#38bdf8"));
    root.setProperty("--web-display-ticker-name", safeColor(ticker.name?.color, "#c4b5fd"));
    root.setProperty("--web-display-ticker-text", safeColor(ticker.text?.color, "#f8fafc"));
    root.setProperty("--web-display-max-width", `${Math.max(320, Math.min(1400, Number(chat.max_width) || 980))}px`);
    root.setProperty("--web-display-media-width", `${Math.max(160, Math.min(1280, Number(styles.media?.max_width) || 760))}px`);
    root.setProperty("--web-display-media-height", `${Math.max(120, Math.min(900, Number(styles.media?.max_height) || 460))}px`);
  }

  function applySettings(next, theme) {
    const previousMode = settings.display_mode;
    settings = {...settings, ...next};
    monitorRoot.dataset.mode = settings.display_mode;
    monitorRoot.dataset.theme = settings.overlay_theme || "default";
    monitorRoot.style.setProperty(
      "--web-display-font-size",
      `${Math.max(12, Number(settings.overlay_font_size) || 24)}px`,
    );
    applyTheme(theme || {});
    if (previousMode !== settings.display_mode) {
      if (renderTimer) window.clearTimeout(renderTimer);
      renderTimer = null;
      stage.replaceChildren();
      rendering = false;
      renderNext();
    }
  }

  function renderNext() {
    if (rendering || queue.length === 0) return;
    rendering = true;
    const message = queue.shift();
    queuedIds.delete(message.id);
    const crawling = settings.display_mode === "crawling";
    const element = messageElement(message, crawling);
    stage.replaceChildren(element);

    if (crawling) {
      requestAnimationFrame(() => {
        const distance = window.innerWidth + element.getBoundingClientRect().width;
        const speed = Math.max(1, Number(settings.scroll_speed_px) || 3) * 60;
        element.style.setProperty("--ticker-duration", `${Math.max(3, distance / speed)}s`);
        element.classList.add("is-running");
      });
      element.addEventListener("animationend", () => {
        stage.replaceChildren();
        rendering = false;
        renderNext();
      }, {once: true});
      return;
    }

    renderTimer = window.setTimeout(() => {
      stage.replaceChildren();
      rendering = false;
      renderTimer = null;
      renderNext();
    }, Math.max(1, Number(settings.display_duration_sec) || 8) * 1000);
  }

  function enqueue(messages) {
    for (const message of messages || []) {
      if (!message?.id || queuedIds.has(message.id)) continue;
      queuedIds.add(message.id);
      queue.push(message);
    }
    renderNext();
  }

  async function exchangeFragmentToken() {
    const token = window.location.hash.slice(1);
    if (!token) return;
    window.history.replaceState(null, "", window.location.pathname);
    const response = await fetch(monitorRoot.dataset.accessUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({token}),
    });
    if (!response.ok) throw new Error("monitor access denied");
  }

  async function poll() {
    try {
      const url = new URL(monitorRoot.dataset.feedUrl, window.location.origin);
      if (cursor) url.searchParams.set("cursor", cursor);
      const response = await fetch(url, {credentials: "same-origin", cache: "no-store"});
      if (!response.ok) {
        if (response.status === 401) accessError.hidden = false;
        throw new Error(`monitor feed ${response.status}`);
      }
      accessError.hidden = true;
      const payload = await response.json();
      cursor = payload.cursor || cursor;
      applySettings(payload.settings || {}, payload.theme || {});
      enqueue(payload.messages || []);
      failures = 0;
      window.setTimeout(poll, Math.max(1, payload.next_poll_after_sec || 3) * 1000);
    } catch (_error) {
      failures += 1;
      window.setTimeout(poll, Math.min(60, 3 * (2 ** Math.min(failures, 4))) * 1000);
    }
  }

  exchangeFragmentToken().then(poll).catch(() => {
    accessError.hidden = false;
  });
}
