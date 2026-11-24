/* Photo size tool (sugarmount21.com): fits a photo under a byte limit as JPEG, in the browser only.
   No upload, no fetch, no libraries. Strings come from the page ([data-m] elements), so ko/en share this file.
   KB = 1000 bytes. Quality is binary-searched between Q_MIN and Q_MAX; below Q_MIN the pixels shrink instead.
   Never upscales. The result is checked with blob.size before it is offered. */
(function () {
  "use strict";
  var root = document.querySelector('[data-tool="photo-size"]');
  if (!root || !window.HTMLCanvasElement || !window.Blob || !window.URL) return;
  var $ = function (s) { return root.querySelector(s); };
  var form = $("form"), file = $("#ps-file"), custom = $("#ps-custom"), shift = $("#ps-shift"),
      status = $("[data-status]"), heic = $("[data-heic]"), out = $("[data-result]"), drop = $("[data-drop]");
  var Q_MAX = 0.92, Q_MIN = 0.4, MAX_PX = 16e6, MIN_EDGE = 64, KB = 1000;
  var lang = document.documentElement.lang === "en" ? "en-US" : "ko-KR";
  var tpl = $("template[data-msgs]"), msgs = tpl && tpl.content ? tpl.content : root;
  var img = null, src = null, run = 0, urls = [];

  function msg(k, v) {
    var e = msgs.querySelector('[data-m="' + k + '"]'), t = e ? e.textContent : k;
    return t.replace(/\{(\w+)\}/g, function (_, n) { return v && n in v ? v[n] : ""; });
  }
  function num(n) { return n.toLocaleString(lang); }
  function kb(n) { return (n / KB).toLocaleString(lang, { maximumFractionDigits: 1 }); }
  function size(n) { return msg("bytes", { b: num(n), k: kb(n) }); }
  function px(w, h) { return msg("px", { w: num(w), h: num(h) }); }
  function say(t, bad) { status.textContent = t; status.classList.toggle("is-error", !!bad); }
  function revoke() { while (urls.length) URL.revokeObjectURL(urls.pop()); }

  function target() {
    var c = form.querySelector('input[name="ps-target"]:checked');
    if (!c) return 0;
    if (c.value !== "custom") return +c.value * KB;
    var v = Math.round(+custom.value);
    return v >= 20 && v <= 20000 ? v * KB : 0;
  }
  function ratio() {
    var c = form.querySelector('input[name="ps-crop"]:checked');
    return c && c.value !== "none" ? c.value.split(":").map(Number) : null;
  }

  function isHeic(f) { return /\.(heic|heif)$/i.test(f.name) || /hei[cf]/i.test(f.type); }

  function load(f) {
    revoke(); out.hidden = true; heic.hidden = true; img = null; src = f;
    if (!f) return;
    if (f.type && !/^image\//.test(f.type) && !isHeic(f)) { say(msg("bad"), true); return; }
    var u = URL.createObjectURL(f), im = new Image();
    im.onload = function () {
      URL.revokeObjectURL(u);
      if (!im.naturalWidth) return fail();
      img = im; go();
    };
    im.onerror = function () { URL.revokeObjectURL(u); fail(); };
    say(msg("read"));
    im.src = u;
    function fail() {
      if (isHeic(f)) { heic.hidden = false; say(msg("heic"), true); } else say(msg("bad"), true);
    }
  }

  function toBlob(cv, q) {
    return new Promise(function (ok) { cv.toBlob(ok, "image/jpeg", q); });
  }

  // Source rectangle: the whole photo, or the largest box of the ratio p:q (k units of p×q), centred by default and
  // moved along the cut axis by the crop-position slider. r[2], when set, caps k (7:9:59 = 413×531 px, passport).
  function rect(W, H, r) {
    if (!r) return { x: 0, y: 0, w: W, h: H, p: 0, cap: 1 };
    var k = Math.floor(Math.min(W / r[0], H / r[1])), w = k * r[0], h = k * r[1], t = (+shift.value || 0) / 100;
    return { x: Math.round((W - w) * t), y: Math.round((H - h) * t), w: w, h: h, p: r, k: k,
             cap: r[2] && k > r[2] ? r[2] / k : 1 };
  }

  async function encode(s, t, id) {
    var scale = Math.min(1, s.cap, Math.sqrt(MAX_PX / (s.w * s.h))), cv = document.createElement("canvas"),
        cx = cv.getContext("2d"), best = null, shrunk = false, w, h;
    for (var tries = 0; tries < 24; tries++) {
      if (s.p) { var k = Math.max(1, Math.floor(s.k * scale + 1e-9)); w = k * s.p[0]; h = k * s.p[1]; }
      else { w = Math.max(1, Math.round(s.w * scale)); h = Math.max(1, Math.round(s.h * scale)); }
      if (Math.max(w, h) < MIN_EDGE) return null;
      cv.width = w; cv.height = h;
      cx.fillStyle = "#fff"; cx.fillRect(0, 0, w, h);  // transparent PNG/WebP areas become white, as in the app
      cx.imageSmoothingQuality = "high";
      cx.drawImage(img, s.x, s.y, s.w, s.h, 0, 0, w, h);
      var b = await toBlob(cv, Q_MAX);
      if (id !== run) return 0;
      if (b && b.size <= t) return { b: b, w: w, h: h, q: Q_MAX, scaled: shrunk };
      var lo = await toBlob(cv, Q_MIN);
      if (id !== run) return 0;
      if (!lo) return null;
      if (lo.size <= t) {
        best = { b: lo, w: w, h: h, q: Q_MIN, scaled: shrunk };
        var a = Q_MIN, z = Q_MAX;
        for (var i = 0; i < 7; i++) {
          var m = (a + z) / 2, mb = await toBlob(cv, m);
          if (id !== run) return 0;
          if (mb && mb.size <= t) { best = { b: mb, w: w, h: h, q: m, scaled: shrunk }; a = m; } else z = m;
        }
        return best;
      }
      // still too big at the lowest quality: shrink the pixels by the byte ratio (bytes ~ pixel count), at least 10 %
      scale *= Math.max(0.5, Math.min(0.9, Math.sqrt(t / lo.size) * 0.97)); shrunk = true;
    }
    return null;
  }

  async function go() {
    if (!img) return;
    var t = target(), id = ++run;
    revoke(); out.hidden = true;  // never leave a result on screen that does not match the current settings
    if (!t) { say(msg("range"), custom.value !== ""); return; }
    var W = img.naturalWidth, H = img.naturalHeight, r = ratio(), s = rect(W, H, r), res;
    shift.closest("[data-shift]").hidden = !r;
    if (!r && src.size <= t && /^image\/jpe?g$/i.test(src.type)) {
      res = { b: src, w: W, h: H, same: true };  // already small enough: hand back the original bytes untouched
    } else {
      say(msg("work"));
      res = await encode(s, t, id);
      if (res === 0) return;  // a newer run took over
    }
    if (!res || res.b.size > t) { say(msg("fail", { t: size(t) }), true); return; }
    show(res, t, W, H);
  }

  function show(res, t, W, H) {
    var u = URL.createObjectURL(res.b); urls.push(u);
    $("[data-o-size]").textContent = size(src.size);
    $("[data-o-px]").textContent = px(W, H);
    $("[data-r-size]").textContent = size(res.b.size);
    $("[data-r-px]").textContent = px(res.w, res.h);
    var fig = $("[data-preview]"), im = new Image();
    im.src = u; im.width = res.w; im.height = res.h; im.alt = msg("alt", { px: px(res.w, res.h) });
    im.decoding = "async";
    fig.replaceChildren(im);
    var base = (src.name || "photo").replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80) || "photo";
    var a = document.createElement("a");
    a.className = "button"; a.href = u; a.download = base + "-" + t / KB + "kb.jpg";
    a.textContent = msg("save", { name: a.download });
    $("[data-dl]").replaceChildren(a);
    out.hidden = false;
    say(msg(res.same ? "same" : "done", { t: size(t), r: size(res.b.size), px: px(res.w, res.h) }) +
        (res.scaled ? " " + msg("scaled") : ""));
  }

  // wiring
  root.querySelectorAll("[data-nojs]").forEach(function (e) { e.remove(); });
  form.hidden = false;
  form.addEventListener("submit", function (e) { e.preventDefault(); go(); });
  file.addEventListener("change", function () { load(file.files[0]); });
  form.addEventListener("change", function (e) {
    if (e.target === file) return;
    go();
  });
  custom.addEventListener("focus", function () { $("#ps-t-custom").checked = true; });
  ["dragenter", "dragover"].forEach(function (n) {
    drop.addEventListener(n, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
  });
  ["dragleave", "drop"].forEach(function (n) {
    drop.addEventListener(n, function () { drop.classList.remove("is-over"); });
  });
  drop.addEventListener("drop", function (e) {
    e.preventDefault();
    var f = e.dataTransfer && e.dataTransfer.files[0];
    if (f) load(f);
  });
})();
