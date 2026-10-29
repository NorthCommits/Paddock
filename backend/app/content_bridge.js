/*
  Paddock page helper. The content server adds this to every HTML page it serves.

  It does nothing unless the page is shown inside the Paddock app, and it only listens to messages
  from the app's own origin (set in data-app-origin on its script tag). It does three things:

    1. Update: when the app sends a new version's address, fetch it and change only the parts that
       differ, so the page does not reload. If that is not safe, it asks the app to reload instead.
    2. Comment: show a small button beside the part of the page under the pointer, and a Comment
       button beside any selected text. Either one sends an "anchor" to the app.
    3. Show: scroll to and flash the part of the page an anchor points at, and draw numbered
       markers where open comments are.
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
    "</style>" +
    '<div class="hl"></div>' +
    '<button class="add" type="button" aria-label="Comment on this part" title="Comment on this part">+</button>' +
    '<button class="sel" type="button">Comment</button>' +
    '<div class="marks"></div>';
  var hl = ui.querySelector(".hl");
  var addBtn = ui.querySelector(".add");
  var selBtn = ui.querySelector(".sel");
  var markBox = ui.querySelector(".marks");
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

  function anchorFor(el, selected) {
    var tag = el.tagName.toLowerCase();
    var text = tag === "img" ? el.getAttribute("alt") || "Image" : norm(el.textContent);
    var a = { v: 1, kind: selected ? "text" : "block", tag: tag, quote: text.slice(0, 200), selector: pathTo(el).slice(0, 240) };
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
    addBtn.style.left = Math.max(x, 4) + "px";
    addBtn.style.top = Math.max(b.t - 2, 4) + "px";
    addBtn.style.display = "block";
  }

  function hideHover() {
    current = null;
    hl.style.display = "none";
    addBtn.style.display = "none";
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

  // ------------------------------------------------------------------ show and markers

  var marks = [];
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
      markBox.appendChild(btn);
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
      marks = m.marks;
      queueMarks();
    } else if (m.type === "show") show(m.anchor);
  });

  send({ type: "ready" });
})();
