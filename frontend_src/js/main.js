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
  let activeTheme = {};

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

  function textElement(className, text, formatted = false) {
    const element = document.createElement("div");
    element.className = className;
    if (formatted) appendFormattedText(element, text);
    else element.textContent = text;
    return element;
  }

  function mediaElement(message, className = "web-display-media") {
    if (message.media_url) {
      const image = document.createElement("img");
      image.className = className;
      image.src = message.media_url;
      image.alt = message.sticker_emoji || "Nachrichtenmedium";
      return image;
    }
    return null;
  }

  function templateContent(message, theme) {
    const container = document.createElement("div");
    container.className = "web-display-frame-content";
    const elements = theme?.chat?.template?.elements || [
      {field: "display_name", style: "name", margin_bottom: 4},
      {field: "content", style: "message", margin_bottom: 10},
      {field: "media", style: "media"},
    ];
    const allowedFields = new Set(["display_name", "content", "media", "sticker_emoji"]);

    for (const item of elements.slice(0, 16)) {
      if (!allowedFields.has(item?.field)) continue;
      let element = null;
      if (item.field === "display_name" && message.display_name) {
        element = textElement("web-display-name", message.display_name);
      } else if (item.field === "content" && message.content) {
        element = textElement("web-display-content", message.content, true);
      } else if (item.field === "media") {
        element = mediaElement(message);
      } else if (item.field === "sticker_emoji" && message.sticker_emoji) {
        element = textElement("web-display-sticker", message.sticker_emoji);
      }
      if (!element) continue;
      element.dataset.themeStyle = String(item.style || "");
      element.style.marginBottom = `${Math.max(0, Math.min(200, Number(item.margin_bottom) || 0))}px`;
      container.append(element);
    }
    return container;
  }

  function messageElement(message, ticker = false, theme = {}) {
    const element = document.createElement("article");
    element.className = ticker ? "web-display-ticker" : "web-display-message";
    element.dataset.messageId = message.id;

    if (ticker) {
      const track = document.createElement("div");
      track.className = "web-display-ticker-track";
      track.append(textElement("web-display-name", message.display_name || "Anonymous"));
      if (message.content) {
        track.append(textElement("web-display-content", message.content, true));
      }
      element.append(track);
      return element;
    }

    const content = templateContent(message, theme);
    const frame = theme?.chat?.background?.frame;
    if (frame?.type === "segmented_vertical") {
      element.classList.add("has-segmented-frame");
      const top = document.createElement("div");
      top.className = "web-display-frame-top";
      const middle = document.createElement("div");
      middle.className = "web-display-frame-middle";
      const bottom = document.createElement("div");
      bottom.className = "web-display-frame-bottom";
      middle.append(content);
      element.append(top, middle, bottom);
    } else {
      element.append(content);
    }
    return element;
  }

  function safeColor(value, fallback) {
    return /^#[0-9a-f]{6}$/i.test(String(value || "")) ? value : fallback;
  }

  function safeAssetUrl(value) {
    try {
      const url = new URL(String(value || ""), window.location.origin);
      return url.origin === window.location.origin ? `url("${url.href}")` : "none";
    } catch (_error) {
      return "none";
    }
  }

  function boundedNumber(value, fallback, minimum, maximum) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.max(minimum, Math.min(maximum, parsed)) : fallback;
  }

  function applyTheme(theme) {
    const chat = theme?.chat || {};
    const chatBackground = chat.background || {};
    const styles = chat.styles || {};
    const ticker = theme?.ticker || {};
    const tickerBackground = ticker.background || {};
    const root = monitorRoot.style;
    root.setProperty("--web-display-canvas", safeColor(theme?.canvas?.background_color, "#0f172a"));
    root.setProperty("--web-display-accent", safeColor(theme?.canvas?.background_accent, theme?.canvas?.background_color || "#333333"));
    root.setProperty("--web-display-bubble", safeColor(chatBackground.color, "#f8fafc"));
    root.setProperty("--web-display-border", safeColor(chatBackground.border_color, "#38bdf8"));
    root.setProperty("--web-display-name", safeColor(styles.name?.color, "#5b21b6"));
    root.setProperty("--web-display-text", safeColor(styles.message?.color, "#111827"));
    root.setProperty("--web-display-name-size", `${boundedNumber(styles.name?.font_size, 30, 10, 96)}px`);
    root.setProperty("--web-display-message-size", `${boundedNumber(styles.message?.font_size, 28, 10, 96)}px`);
    root.setProperty("--web-display-ticker", safeColor(tickerBackground.color, "#172033"));
    root.setProperty("--web-display-ticker-border", safeColor(tickerBackground.border_color, "#38bdf8"));
    root.setProperty("--web-display-ticker-name", safeColor(ticker.name?.color, ticker.text?.color || "#ffffff"));
    root.setProperty("--web-display-ticker-text", safeColor(ticker.text?.color, "#f8fafc"));
    root.setProperty("--web-display-max-width", `${boundedNumber(chat.max_width, 980, 320, 1400)}px`);
    root.setProperty("--web-display-media-width", `${boundedNumber(styles.media?.max_width, 760, 160, 1280)}px`);
    root.setProperty("--web-display-media-height", `${boundedNumber(styles.media?.max_height, 460, 120, 900)}px`);
    root.setProperty("--web-display-chat-scale", boundedNumber(chat.scale, 1, 0.1, 2));
    root.setProperty("--web-display-chat-x", `${boundedNumber(chat.position?.x, 40, -1920, 1920)}px`);
    root.setProperty("--web-display-chat-y", `${boundedNumber(chat.position?.y, 40, -1080, 1080)}px`);
    root.setProperty("--web-display-frame-padding-x", `${boundedNumber(chatBackground.padding?.x, 36, 0, 200)}px`);
    root.setProperty("--web-display-frame-padding-y", `${boundedNumber(chatBackground.padding?.y, 28, 0, 200)}px`);
    root.setProperty("--web-display-frame-top-height", `${boundedNumber(theme?.assets?.[chatBackground.frame?.top]?.height, 0, 0, 400)}px`);
    root.setProperty("--web-display-frame-middle-height", `${boundedNumber(theme?.assets?.[chatBackground.frame?.middle]?.height, 1, 1, 400)}px`);
    root.setProperty("--web-display-frame-bottom-height", `${boundedNumber(theme?.assets?.[chatBackground.frame?.bottom]?.height, 0, 0, 400)}px`);
    root.setProperty("--web-display-frame-top", safeAssetUrl(theme?.assets?.[chatBackground.frame?.top]?.url));
    root.setProperty("--web-display-frame-middle", safeAssetUrl(theme?.assets?.[chatBackground.frame?.middle]?.url));
    root.setProperty("--web-display-frame-bottom", safeAssetUrl(theme?.assets?.[chatBackground.frame?.bottom]?.url));
    root.setProperty("--web-display-ticker-scale", boundedNumber(ticker.scale, 1, 0.1, 2));
    root.setProperty("--web-display-ticker-x", `${boundedNumber(ticker.position?.x, 32, -1920, 1920)}px`);
    const tickerY = boundedNumber(ticker.position?.y, -104, -1080, 1080);
    root.setProperty("--web-display-ticker-y", `${Math.abs(tickerY)}px`);
    const tickerWidth = Number(ticker.width);
    root.setProperty(
      "--web-display-ticker-width",
      tickerWidth < 0
        ? `calc(100vw - ${Math.abs(tickerWidth)}px)`
        : `${boundedNumber(tickerWidth, 1200, 120, 1920)}px`,
    );
  }

  function applySettings(next, theme) {
    const previousMode = settings.display_mode;
    settings = {...settings, ...next};
    activeTheme = theme || {};
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
    const element = messageElement(message, crawling, activeTheme);
    stage.replaceChildren(element);

    if (crawling) {
      requestAnimationFrame(() => {
        const track = element.querySelector(".web-display-ticker-track");
        const distance = element.getBoundingClientRect().width + track.getBoundingClientRect().width;
        const refreshRate = boundedNumber(activeTheme?.display_profile?.refresh_rate, 50, 1, 240);
        const speed = Math.max(1, Number(settings.scroll_speed_px) || 3) * refreshRate;
        element.style.setProperty("--ticker-duration", `${Math.max(3, distance / speed)}s`);
        element.style.setProperty("--ticker-distance", `${-distance}px`);
        element.classList.add("is-running");
      });
      element.querySelector(".web-display-ticker-track").addEventListener("animationend", () => {
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
