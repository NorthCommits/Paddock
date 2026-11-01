/*
  Paddock page helper. The content server adds this to every HTML page it serves.

  It does nothing unless the page is shown inside the Paddock app, and it only listens to messages
  from the app's own origin (set in data-app-origin on its script tag). It does these things:

    1. Update: when the app sends a new version's address, fetch it and change only the parts that
       differ, so the page does not reload. If that is not safe, it asks the app to reload instead.
    2. Comment: show a small button beside the part of the page under the pointer, and a Comment
       button beside any selected text. Either one sends an "anchor" to the app.
    3. Show: scroll to and flash the part of the page an anchor points at, and draw numbered
       markers where open comments are. A marker shows a small preview card when hovered.
    4. Live page: name each part (data-pd-id, or a name made from its words) so comments, reactions
       and other people's places keep pointing at the right part. In comment mode a click on a part
       comments on it. Others' places and reactions are drawn here; the app sends them in.
*/
(function () {
  "use strict";
  if (window.parent === window) return;
  var me = document.currentScript;
  var APP = me && me.getAttribute("data-app-origin");
  if (!APP) return;

  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var VISUAL = /^(img|svg|canvas|video|picture|figure|iframe)$/;
  var INDIGO = "59, 51, 201";
  var ID_OK = /^[A-Za-z0-9_-]{1,64}$/;
  var COLOR_OK = /^#[0-9a-fA-F]{6}$/;
  // Small line icons, drawn here so no emoji or picture files are needed.
  var ICON = {
    like: '<svg viewBox="0 0 24 24"><path d="M7 11v9H4v-9zM7 11l4-8c1.6 0 2.5 1.2 2.2 2.8L12.7 9H19a2 2 0 0 1 2 2.3l-1 6.5A2 2 0 0 1 18 19.5H7"/></svg>',
    love: '<svg viewBox="0 0 24 24"><path d="M12 20s-8-4.6-8-10.5A4.5 4.5 0 0 1 12 7a4.5 4.5 0 0 1 8 2.5C20 15.4 12 20 12 20z"/></svg>',
    cheer: '<svg viewBox="0 0 24 24"><path d="M12 3l2.2 5.6L20 9.3l-4.4 3.9 1.4 5.8L12 15.8 7 19l1.4-5.8L4 9.3l5.8-.7z"/></svg>',
    eyes: '<svg viewBox="0 0 24 24"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.8"/></svg>',
  };
  var LABEL = { like: "Like", love: "Love", cheer: "Cheer", eyes: "Looking" };
  var KEYS = ["like", "love", "cheer", "eyes"];

  function send(msg) {
    msg.paddock = true;
    window.parent.postMessage(msg, APP);
  }
  function norm(s) {
    return String(s || "").replace(/\s+/g, " ").trim();
  }

  // ------------------------------------------------------------------ overlay

  var host = document.createElement("div");
  host.setAttribute("data-paddock-ui", "");
  host.style.cssText = "position:absolute;top:0;left:0;width:0;height:0;z-index:2147483647;";
  var ui = host.attachShadow({ mode: "open" });
  ui.innerHTML =
    "<style>" +
    ".hl{position:absolute;display:none;pointer-events:none;border-radius:4px;" +
    "outline:2px dashed rgba(" + INDIGO + ",.6);background:rgba(" + INDIGO + ",.06)}" +
    "button{position:absolute;display:none;cursor:pointer;border:0;font:600 13px/1 system-ui,sans-serif;" +
    "color:#fff;background:rgb(" + INDIGO + ");box-shadow:0 2px 8px rgba(15,17,40,.35)}" +
    "button:hover{background:#2f28a8}button:focus-visible{outline:3px solid #ff6b4a;outline-offset:2px}" +
    ".add{width:28px;height:28px;border-radius:50%;font-size:18px;padding:0}" +
    ".sel{height:30px;padding:0 12px;border-radius:15px;background:#0f1115}.sel:hover{background:#2a2e38}" +
    ".mark{display:block;min-width:22px;height:22px;border-radius:11px;padding:0 6px;font-size:12px;" +
    "background:#ff6b4a;color:#0f1115;box-shadow:0 1px 4px rgba(15,17,40,.4)}" +
    ".mark:hover{background:#ff8265}" +
    ".hl.pin{outline:2px solid rgba(" + INDIGO + ",.85);background:rgba(" + INDIGO + ",.1)}" +
    ".peer{position:absolute;pointer-events:none;border-radius:4px;transition:opacity 180ms ease}" +
    ".tag{position:absolute;top:-20px;left:-2px;padding:2px 7px;border-radius:4px 4px 4px 0;font:600 11px/16px system-ui,sans-serif;" +
    "color:#fff;white-space:nowrap;max-width:160px;overflow:hidden;text-overflow:ellipsis}" +
    ".chips{position:absolute;display:flex;gap:4px;transform:translateX(-100%)}" +
    ".chip,.pick button{position:static;display:inline-flex;align-items:center;gap:4px;height:22px;padding:0 7px;border-radius:11px;" +
    "font:600 12px/1 system-ui,sans-serif;color:#1f2230;background:#fff;box-shadow:0 0 0 1px rgba(15,17,40,.18),0 1px 3px rgba(15,17,40,.2)}" +
    ".chip:hover,.pick button:hover{background:#eef0ff}" +
    ".chip.mine{background:#e6e8ff;box-shadow:0 0 0 1.5px rgb(" + INDIGO + ")}" +
    ".chip svg,.pick svg,.react svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}" +
    ".react{width:28px;height:28px;border-radius:50%;padding:0;color:#fff}" +
    ".react svg{margin:7px}" +
    ".pick{position:absolute;display:none;gap:2px;padding:4px;border-radius:16px;background:#fff;box-shadow:0 0 0 1px rgba(15,17,40,.15),0 6px 18px rgba(15,17,40,.25)}" +
    ".pick button{height:28px;width:28px;padding:0;justify-content:center;border-radius:14px;box-shadow:none}" +
    "@media (pointer:coarse){.mark{min-width:44px;height:44px;border-radius:22px}.add,.react{width:44px;height:44px}" +
    ".chip{height:44px;min-width:44px;justify-content:center}.pick button{height:44px;width:44px}.sel{height:44px}}" +
    "@media (prefers-reduced-motion:reduce){.peer{transition:none}}" +
    "</style>" +
    '<div class="hl"></div>' +
    '<div class="peers"></div>' +
    '<button class="add" type="button" aria-label="Comment on this part" title="Comment on this part">+</button>' +
    '<button class="react" type="button" aria-label="React to this part" title="React to this part">' + ICON.like + "</button>" +
    '<div class="pick"></div>' +
    '<button class="sel" type="button">Comment</button>' +
    '<div class="marks"></div>' +
    '<div class="chipbox"></div>';
  var hl = ui.querySelector(".hl");
  var addBtn = ui.querySelector(".add");
  var reactBtn = ui.querySelector(".react");
  var pickBox = ui.querySelector(".pick");
  var selBtn = ui.querySelector(".sel");
  var markBox = ui.querySelector(".marks");
  var peerBox = ui.querySelector(".peers");
  var chipBox = ui.querySelector(".chipbox");
  document.documentElement.appendChild(host);

  // ------------------------------------------------------------------ finding parts

  function blockOf(target) {
    var el = target && target.nodeType === 1 ? target : target && target.parentElement;
    while (el && el !== document.body && el !== document.documentElement) {
      if (VISUAL.test(el.tagName.toLowerCase())) break;
      var d = getComputedStyle(el).display;
      if (d.indexOf("inline") !== 0 && d !== "contents") break;
      el = el.parentElement;
    }
    if (!el || el === document.body || el === document.documentElement || el === host) return null;
    return anchorable(el) ? el : null;
  }

  function anchorable(el) {
    if (VISUAL.test(el.tagName.toLowerCase())) return true;
    var own = "";
    for (var n = el.firstChild; n; n = n.nextSibling) if (n.nodeType === 3) own += n.nodeValue;
    if (norm(own)) return true;
    if (!norm(el.textContent)) return false;
    for (var c = el.firstElementChild; c; c = c.nextElementSibling) {
      if (getComputedStyle(c).display.indexOf("inline") !== 0) return false;
    }
    return true;
  }

  function pathTo(el) {
    var parts = [];
    while (el && el !== document.body && el !== document.documentElement && parts.length < 8) {
      if (el.id) {
        parts.unshift("#" + CSS.escape(el.id));
        break;
      }
      var tag = el.tagName.toLowerCase();
      var i = 1;
      for (var s = el.previousElementSibling; s; s = s.previousElementSibling) {
        if (s.tagName === el.tagName) i++;
      }
      parts.unshift(tag + ":nth-of-type(" + i + ")");
      el = el.parentElement;
    }
    return parts.join(" > ");
  }

  function sectionOf(el) {
    var heads = document.querySelectorAll("h1,h2,h3,h4,h5,h6");
    var found = null;
    for (var i = 0; i < heads.length; i++) {
      if (heads[i] === el) return null;
      if (heads[i].compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) found = heads[i];
    }
    return found ? norm(found.textContent).slice(0, 100) : null;
  }

  // Stable block ids. A part with data-pd-id keeps that name for ever. Any other part is named from its
  // tag and first words, so the same part gets the same name for everyone who views the same version.
  var idByEl = new Map();
  var elById = new Map();
  var idsDirty = true;
  var builtAt = 0;

  function isBlock(el) {
    if (el === host || host.contains(el)) return false;
    var d = getComputedStyle(el).display;
    if (d.indexOf("inline") === 0 || d === "contents" || d === "none") return false;
    return anchorable(el);
  }

  function hashOf(s) {
    var h = 5381;
    for (var i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
    return h.toString(36);
  }

  function buildIds() {
    idsDirty = false;
    builtAt = Date.now();
    idByEl = new Map();
    elById = new Map();
    var seen = {};
    var all = document.body ? document.body.querySelectorAll("*") : [];
    for (var i = 0; i < all.length && i < 3000; i++) {
      var el = all[i];
      var given = el.getAttribute("data-pd-id");
      var id = null;
      if (given && ID_OK.test(given) && !elById.has(given)) {
        id = given;
      } else if (isBlock(el)) {
        var tag = el.tagName.toLowerCase();
        var base = "b-" + hashOf(tag + "|" + (tag === "img" ? el.getAttribute("alt") || "" : norm(el.textContent).slice(0, 120)));
        seen[base] = (seen[base] || 0) + 1;
        id = seen[base] > 1 ? base + "-" + seen[base] : base;
        if (elById.has(id)) id = null;
      }
      if (id) {
        idByEl.set(el, id);
        elById.set(id, el);
      }
    }
  }

  function ids() {
    // A busy page (animation, a clock) must not make every pointer move rebuild the names.
    if (idsDirty && Date.now() - builtAt > 400) buildIds();
    return idByEl;
  }
  function idOf(el) {
    return ids().get(el) || null;
  }
  function byId(id) {
    ids();
    return elById.get(id) || null;
  }
  if (window.MutationObserver) {
    new MutationObserver(function () {
      idsDirty = true;
    }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["data-pd-id"] });
  }

  function anchorFor(el, selected) {
    var tag = el.tagName.toLowerCase();
    var text = tag === "img" ? el.getAttribute("alt") || "Image" : norm(el.textContent);
    var a = { v: 1, kind: selected ? "text" : "block", tag: tag, quote: text.slice(0, 200), selector: pathTo(el).slice(0, 240) };
    var id = idOf(el);
    if (id) a.id = id;
    if (selected) a.selected = norm(selected).slice(0, 240);
    var section = sectionOf(el);
    if (section) a.section = section;
    return a;
  }

  function findAnchor(a) {
    if (!a) return null;
    var want = norm(a.quote).slice(0, 80).toLowerCase();
    function fits(el) {
      if (!el || host.contains(el)) return false;
      if (a.tag && el.tagName.toLowerCase() !== a.tag) return false;
      if (!want || a.tag === "img") return true;
      return norm(el.textContent).toLowerCase().indexOf(want) !== -1;
    }
    var el = null;
    // A name with a count on the end ("b-x-2") depends on what else is on screen, so the path goes first.
    if (a.id && ID_OK.test(a.id) && !/^b-[0-9a-z]+-\d+$/.test(a.id)) {
      el = byId(a.id);
      // A named part is trusted even if its words changed. A computed name only matches the same words.
      if (el && (!a.tag || el.tagName.toLowerCase() === a.tag)) {
        if (el.hasAttribute("data-pd-id") || fits(el)) return el;
      }
    }
    try {
      el = a.selector ? document.querySelector(a.selector) : null;
    } catch (e) {
      el = null;
    }
    if (fits(el)) return el;
    if (!want) return null;
    var all = document.body.querySelectorAll(a.tag || "*");
    for (var i = 0; i < all.length; i++) if (fits(all[i])) return all[i];
    // The words were edited (maybe because of this very comment). If the same kind of part still sits
    // at the same place under the same heading, it is almost certainly the one.
    try {
      el = a.selector ? document.querySelector(a.selector) : null;
    } catch (e) {
      el = null;
    }
    if (el && !host.contains(el) && (!a.tag || el.tagName.toLowerCase() === a.tag) && (!a.section || sectionOf(el) === a.section)) return el;
    return null;
  }

  // ------------------------------------------------------------------ flash

  function flash(el, strong) {
    if (calm || !el || !el.animate) return;
    var on = strong ? 0.28 : 0.18;
    try {
      el.animate(
        [
          { backgroundColor: "rgba(" + INDIGO + "," + on + ")", outline: "2px solid rgba(" + INDIGO + ",.6)", outlineOffset: "3px" },
          { backgroundColor: "rgba(" + INDIGO + ",0)", outline: "2px solid rgba(" + INDIGO + ",0)", outlineOffset: "3px" },
        ],
        { duration: strong ? 2200 : 1600, easing: "ease-out" }
      );
    } catch (e) {
      /* a decorative effect only */
    }
  }

  // ------------------------------------------------------------------ shared state

  var mode = false; // comment mode: a tap or click on a part comments on it
  var sharing = false; // the reader lets others see which part they look at
  var canReact = false;
  var reacts = [];
  var peers = [];
  var peersSig = "";
  var reactSig = "";
  var focusTimer = 0;
  var focusWant = null;
  var focusSent = { id: null, kind: "look" };

  // Tells the app which part the reader is on (never the words), at most four times a second.
  function report(id, kind) {
    if (!sharing) return;
    focusWant = { id: id, kind: kind };
    if (focusTimer) return;
    focusTimer = setTimeout(function () {
      focusTimer = 0;
      var w = focusWant;
      if (!w || (w.id === focusSent.id && w.kind === focusSent.kind)) return;
      focusSent = w;
      send({ type: "focus", id: w.id, kind: w.kind });
    }, 250);
  }

  function mineFor(id, key) {
    return reacts.some(function (r) {
      return r.block === id && r.key === key && r.mine;
    });
  }

  // ------------------------------------------------------------------ hover button

  var current = null;
  var hideTimer = 0;
  var frameQueued = false;
  var lastEvent = null;

  function box(el) {
    var r = el.getBoundingClientRect();
    return { l: r.left + pageXOffset, t: r.top + pageYOffset, w: r.width, h: r.height };
  }

  function showFor(el) {
    var b = box(el);
    hl.style.cssText = "display:block;left:" + (b.l - 4) + "px;top:" + (b.t - 3) + "px;width:" + (b.w + 8) + "px;height:" + (b.h + 6) + "px";
    var x = b.l - 36;
    if (x < pageXOffset + 4) x = b.l + b.w + 8;
    if (x > pageXOffset + document.documentElement.clientWidth - 34) x = b.l + b.w - 32;
    var top = Math.max(b.t - 2, 4);
    hl.className = mode ? "hl pin" : "hl";
    addBtn.style.left = Math.max(x, 4) + "px";
    addBtn.style.top = top + "px";
    addBtn.style.display = mode ? "none" : "block";
    var id = idOf(el);
    if (canReact && id && !mode) {
      reactBtn.style.left = Math.max(x, 4) + "px";
      reactBtn.style.top = top + 32 + "px";
      reactBtn.style.display = "block";
    } else {
      reactBtn.style.display = "none";
    }
  }

  function hideHover() {
    current = null;
    hl.style.display = "none";
    addBtn.style.display = "none";
    reactBtn.style.display = "none";
    report(null, "look");
  }

  function onMove() {
    frameQueued = false;
    var e = lastEvent;
    if (!e || selBtn.style.display === "block") return;
    if (e.target === host) return;
    var el = blockOf(e.target);
    if (el === current) return;
    clearTimeout(hideTimer);
    if (el) {
      current = el;
      showFor(el);
      report(idOf(el), "look");
    } else {
      hideTimer = setTimeout(hideHover, 450);
    }
  }

  document.addEventListener(
    "mousemove",
    function (e) {
      lastEvent = e;
      if (!frameQueued) {
        frameQueued = true;
        requestAnimationFrame(onMove);
      }
    },
    { passive: true }
  );
  document.documentElement.addEventListener("mouseleave", function () {
    hideTimer = setTimeout(hideHover, 450);
  });
  host.addEventListener("mouseenter", function () {
    clearTimeout(hideTimer);
  });
  window.addEventListener("resize", hideHover);

  addBtn.addEventListener("click", function () {
    if (current) send({ type: "comment", anchor: anchorFor(current, "") });
  });

  // ------------------------------------------------------------------ selection button

  var picked = null;
  var selTimer = 0;

  function checkSelection() {
    var sel = window.getSelection();
    var text = sel ? norm(sel.toString()) : "";
    if (!sel || sel.isCollapsed || text.length < 2) {
      selBtn.style.display = "none";
      if (picked) report(current ? idOf(current) : null, "look");
      picked = null;
      return;
    }
    var node = sel.getRangeAt(0).commonAncestorContainer;
    var el = blockOf(node);
    if (!el) {
      selBtn.style.display = "none";
      picked = null;
      return;
    }
    var rects = sel.getRangeAt(0).getClientRects();
    var last = rects[rects.length - 1];
    if (!last) return;
    picked = { el: el, text: text };
    hideHover();
    report(idOf(el), "select");
    selBtn.style.left = Math.max(4, last.right + pageXOffset - 40) + "px";
    selBtn.style.top = last.bottom + pageYOffset + 8 + "px";
    selBtn.style.display = "block";
  }

  document.addEventListener("selectionchange", function () {
    clearTimeout(selTimer);
    selTimer = setTimeout(checkSelection, 180);
  });
  selBtn.addEventListener("mousedown", function (e) {
    e.preventDefault(); // keeps the selection while the button is pressed
  });
  selBtn.addEventListener("click", function () {
    if (!picked) return;
    send({ type: "comment", anchor: anchorFor(picked.el, picked.text) });
    flash(picked.el, true);
    selBtn.style.display = "none";
  });

  // ------------------------------------------------------------------ comment mode

  document.addEventListener(
    "click",
    function (e) {
      if (!mode || e.target === host) return;
      var el = blockOf(e.target);
      e.preventDefault();
      e.stopPropagation();
      if (!el) return;
      flash(el, true);
      send({ type: "comment", anchor: anchorFor(el, "") });
    },
    true
  );
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && mode) send({ type: "mode", comment: false });
  });

  // ------------------------------------------------------------------ reactions

  var pickFor = null;

  function closePick() {
    pickFor = null;
    pickBox.style.display = "none";
  }

  function toggle(id, key) {
    if (!canReact || !ID_OK.test(id)) return;
    send({ type: "react", block: id, key: key, on: !mineFor(id, key) });
  }

  KEYS.forEach(function (key) {
    var b = document.createElement("button");
    b.type = "button";
    b.innerHTML = ICON[key];
    b.setAttribute("aria-label", LABEL[key]);
    b.title = LABEL[key];
    b.addEventListener("click", function () {
      if (pickFor) toggle(pickFor, key);
      closePick();
    });
    pickBox.appendChild(b);
  });

  reactBtn.addEventListener("click", function () {
    var id = current && idOf(current);
    if (!id) return;
    pickFor = id;
    pickBox.style.left = reactBtn.style.left;
    pickBox.style.top = parseFloat(reactBtn.style.top) + 32 + "px";
    pickBox.style.display = "flex";
  });
  document.addEventListener("pointerdown", function (e) {
    if (pickFor && e.target !== host) closePick();
  });

  // ------------------------------------------------------------------ show and markers

  var marks = [];
  var marksSig = "";
  var drawQueued = false;

  function drawMarks() {
    drawQueued = false;
    markBox.textContent = "";
    var used = new Map();
    marks.forEach(function (m) {
      var el = findAnchor(m.anchor);
      if (!el) return;
      var b = box(el);
      var k = used.get(el) || 0;
      used.set(el, k + 1);
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "mark";
      btn.textContent = String(m.n);
      btn.setAttribute("aria-label", "Open comment " + m.n);
      btn.title = "Open comment " + m.n;
      var right = document.documentElement.clientWidth + pageXOffset - 26;
      btn.style.left = Math.min(b.l + b.w - 24 - k * 26, right) + "px";
      btn.style.top = Math.max(b.t - 10, 2) + "px";
      btn.addEventListener("click", function () {
        flash(el, true);
        send({ type: "mark", id: m.id });
      });
      // The preview card is drawn by the app, so the comment's words never enter this frame.
      function over() {
        var r = btn.getBoundingClientRect();
        send({ type: "markhover", id: m.id, x: r.right, y: r.bottom });
      }
      function out() {
        send({ type: "markleave" });
      }
      btn.addEventListener("mouseenter", over);
      btn.addEventListener("focus", over);
      btn.addEventListener("mouseleave", out);
      btn.addEventListener("blur", out);
      markBox.appendChild(btn);
    });
    drawPeers();
    drawChips();
  }

  // Others' places: a soft outline in their colour and a name tag, on the part they are looking at.
  function drawPeers() {
    peerBox.textContent = "";
    peers.forEach(function (p) {
      var el = byId(p.block);
      if (!el) return;
      var b = box(el);
      var d = document.createElement("div");
      d.className = "peer";
      var col = p.color;
      var solid = p.kind === "select";
      d.style.cssText =
        "left:" + (b.l - 4) + "px;top:" + (b.t - 3) + "px;width:" + (b.w + 8) + "px;height:" + (b.h + 6) + "px;" +
        "outline:2px " + (solid ? "solid " : "dashed ") + col + ";background:" + col + (solid ? "1f" : "14");
      var t = document.createElement("div");
      t.className = "tag";
      t.style.background = col;
      t.textContent = p.tag;
      d.appendChild(t);
      peerBox.appendChild(d);
    });
  }

  function drawChips() {
    chipBox.textContent = "";
    var groups = {};
    reacts.forEach(function (r) {
      (groups[r.block] = groups[r.block] || []).push(r);
    });
    Object.keys(groups).forEach(function (id) {
      var el = byId(id);
      if (!el) return;
      var b = box(el);
      var row = document.createElement("div");
      row.className = "chips";
      row.style.left = Math.min(b.l + b.w, pageXOffset + document.documentElement.clientWidth - 4) + "px";
      row.style.top = b.t + b.h - 11 + "px";
      groups[id].forEach(function (r) {
        var c = document.createElement("button");
        c.type = "button";
        c.className = r.mine ? "chip mine" : "chip";
        c.innerHTML = ICON[r.key] + "<span></span>";
        c.querySelector("span").textContent = String(r.count);
        c.setAttribute("aria-label", LABEL[r.key] + ", " + r.count + (r.mine ? ", yours" : ""));
        c.setAttribute("aria-pressed", r.mine ? "true" : "false");
        c.addEventListener("click", function () {
          toggle(id, r.key);
        });
        row.appendChild(c);
      });
      chipBox.appendChild(row);
    });
  }
  function queueMarks() {
    if (drawQueued) return;
    drawQueued = true;
    requestAnimationFrame(drawMarks);
  }
  if (window.ResizeObserver) new ResizeObserver(queueMarks).observe(document.documentElement);
  window.addEventListener("load", queueMarks);

  function show(anchor) {
    var el = findAnchor(anchor);
    if (!el) {
      send({ type: "missing" });
      return;
    }
    el.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
    flash(el, true);
  }

  // ------------------------------------------------------------------ update in place

  var changed = 0;

  function kids(n) {
    return Array.prototype.filter.call(n.childNodes, function (c) {
      if (c.nodeType === 3) return c.nodeValue.trim() !== "";
      if (c.nodeType === 8) return false;
      return !(c.nodeType === 1 && c.hasAttribute("data-paddock-bridge"));
    });
  }

  // Like isEqualNode, but blind to the whitespace between tags, which differs between versions.
  function same(x, y) {
    if (x.nodeType !== y.nodeType || x.nodeName !== y.nodeName) return false;
    if (x.nodeType === 3) return norm(x.nodeValue) === norm(y.nodeValue);
    if (x.nodeType !== 1) return true;
    if (x.attributes.length !== y.attributes.length) return false;
    for (var i = 0; i < x.attributes.length; i++) {
      if (y.getAttribute(x.attributes[i].name) !== x.attributes[i].value) return false;
    }
    var a = kids(x);
    var b = kids(y);
    if (a.length !== b.length) return false;
    for (var j = 0; j < a.length; j++) if (!same(a[j], b[j])) return false;
    return true;
  }

  function flashNode(n) {
    flash(n.nodeType === 1 ? n : n.parentElement, false);
  }

  function copyAttributes(x, y) {
    Array.prototype.slice.call(x.attributes).forEach(function (at) {
      if (!y.hasAttribute(at.name)) x.removeAttribute(at.name);
    });
    Array.prototype.forEach.call(y.attributes, function (at) {
      if (x.getAttribute(at.name) !== at.value) x.setAttribute(at.name, at.value);
    });
  }

  function update(x, y) {
    if (x.nodeType !== y.nodeType || x.nodeName !== y.nodeName) {
      var fresh = document.importNode(y, true);
      x.parentNode.replaceChild(fresh, x);
      flashNode(fresh);
      changed++;
      return;
    }
    if (x.nodeType === 3) {
      x.nodeValue = y.nodeValue;
      flashNode(x);
      changed++;
      return;
    }
    copyAttributes(x, y);
    if (same(x, y)) {
      flashNode(x);
      changed++;
      return;
    }
    var hasElement = kids(x).concat(kids(y)).some(function (c) {
      return c.nodeType === 1;
    });
    if (hasElement) {
      morph(x, y);
    } else {
      while (x.firstChild) x.removeChild(x.firstChild);
      Array.prototype.forEach.call(y.childNodes, function (c) {
        x.appendChild(document.importNode(c, true));
      });
      flashNode(x);
      changed++;
    }
  }

  // Makes the children of a look like the children of b, touching only what differs.
  function morph(a, b) {
    var ak = kids(a);
    var bk = kids(b);
    var s = 0;
    while (s < ak.length && s < bk.length && same(ak[s], bk[s])) s++;
    var ae = ak.length;
    var be = bk.length;
    while (ae > s && be > s && same(ak[ae - 1], bk[be - 1])) {
      ae--;
      be--;
    }
    var oldMid = ak.slice(s, ae);
    var newMid = bk.slice(s, be);
    var before = ae < ak.length ? ak[ae] : a.querySelector(":scope > script[data-paddock-bridge]");
    var n = Math.min(oldMid.length, newMid.length);
    for (var i = 0; i < n; i++) update(oldMid[i], newMid[i]);
    for (var j = n; j < oldMid.length; j++) {
      oldMid[j].parentNode.removeChild(oldMid[j]);
      changed++;
    }
    for (var k = n; k < newMid.length; k++) {
      var add = document.importNode(newMid[k], true);
      a.insertBefore(add, before);
      flashNode(add);
      changed++;
    }
  }

  function styleSignature(d) {
    return Array.prototype.map
      .call(d.querySelectorAll("style, link[rel~='stylesheet']"), function (n) {
        return n.outerHTML;
      })
      .join("\n");
  }

  function runs(d) {
    return Array.prototype.filter.call(d.querySelectorAll("script"), function (s) {
      if (s.hasAttribute("data-paddock-bridge")) return false;
      var t = (s.getAttribute("type") || "").toLowerCase();
      return t === "" || t === "module" || t.indexOf("javascript") !== -1;
    });
  }

  function scriptSignature(d) {
    return runs(d)
      .map(function (s) {
        return s.getAttribute("src") ? "src:" + s.getAttribute("src") : "inline:" + s.textContent;
      })
      .join("\u0001");
  }

  function load(url, fresh) {
    return fetch(url, { credentials: "omit", cache: fresh ? "no-store" : "default" }).then(function (r) {
      if (!r.ok) throw new Error("status " + r.status);
      return r.text();
    });
  }
  function parse(html) {
    return new DOMParser().parseFromString(html, "text/html");
  }

  var busy = false;
  var waiting = null;

  function patch(url) {
    if (busy) {
      waiting = url;
      return;
    }
    busy = true;
    Promise.all([load(location.href, false), load(url, true)])
      .then(function (pair) {
        var before = parse(pair[0]);
        var after = parse(pair[1]);
        // Only patch a page that still looks like what the server sent. If scripts or the reader have
        // changed it since, or the new version has different scripts, a reload is the safe way.
        var untouched = same(document.body, before.body);
        var sameScripts = scriptSignature(before) === scriptSignature(after);
        if (!untouched || !sameScripts) {
          send({ type: "reload" });
          return;
        }
        history.replaceState(null, "", new URL(url, location.href).pathname);
        changed = 0;
        if (styleSignature(before) !== styleSignature(after)) {
          var old = document.querySelectorAll("head style, head link[rel~='stylesheet']");
          Array.prototype.forEach.call(after.querySelectorAll("style, link[rel~='stylesheet']"), function (n) {
            var c = document.importNode(n, true);
            if (c.getAttribute("href")) c.setAttribute("href", new URL(c.getAttribute("href"), url).href);
            document.head.appendChild(c);
          });
          setTimeout(function () {
            Array.prototype.forEach.call(old, function (n) {
              n.parentNode && n.parentNode.removeChild(n);
            });
          }, 150);
          changed++;
        }
        if (after.title && document.title !== after.title) document.title = after.title;
        copyAttributes(document.body, after.body);
        morph(document.body, after.body);
        hideHover();
        builtAt = 0;
        queueMarks();
        send({ type: "patched", changed: changed });
      })
      .catch(function () {
        send({ type: "patch-failed" });
      })
      .then(function () {
        busy = false;
        if (waiting) {
          var next = waiting;
          waiting = null;
          patch(next);
        }
      });
  }

  // ------------------------------------------------------------------ messages

  window.addEventListener("message", function (e) {
    if (e.source !== window.parent || e.origin !== APP) return;
    var m = e.data;
    if (!m || m.paddock !== true) return;
    if (m.type === "patch" && typeof m.url === "string") patch(m.url);
    else if (m.type === "marks" && Array.isArray(m.marks)) {
      var sig = JSON.stringify(m.marks);
      if (sig === marksSig) return;
      marksSig = sig;
      marks = m.marks;
      queueMarks();
    } else if (m.type === "show") show(m.anchor);
    else if (m.type === "mode") {
      mode = m.comment === true;
      hideHover();
    } else if (m.type === "share") {
      sharing = m.on === true;
      if (!sharing) {
        focusWant = null;
        focusSent = { id: null, kind: "look" };
      }
    } else if (m.type === "peers" && Array.isArray(m.peers)) {
      if (JSON.stringify(m.peers) === peersSig) return;
      peersSig = JSON.stringify(m.peers);
      peers = m.peers
        .filter(function (p) {
          return p && ID_OK.test(String(p.block)) && COLOR_OK.test(String(p.color)) && typeof p.tag === "string";
        })
        .slice(0, 12)
        .map(function (p) {
          return { block: p.block, color: p.color, tag: p.tag.slice(0, 3), kind: p.kind === "select" ? "select" : "look" };
        });
      queueMarks();
    } else if (m.type === "reactions" && Array.isArray(m.items)) {
      if (JSON.stringify([m.items, m.can]) === reactSig) return;
      reactSig = JSON.stringify([m.items, m.can]);
      canReact = m.can === true;
      reacts = m.items
        .filter(function (r) {
          return r && ID_OK.test(String(r.block)) && KEYS.indexOf(r.key) !== -1 && Number(r.count) > 0;
        })
        .slice(0, 400)
        .map(function (r) {
          return {
            block: r.block,
            key: r.key,
            count: Number(r.count),
            mine: r.mine === true,
          };
        });
      if (current) showFor(current); // the react button may now be allowed, or not
      queueMarks();
    }
  });

  send({ type: "ready" });
})();
