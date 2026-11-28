/* HEIC to JPG tool (sugarmount21.com): converts HEIC/HEIF (and any image the browser reads) to JPEG, in the browser only.
   The browser's own decoder is tried first (Safari reads HEIC). Only when that fails on a HEIC file is the libheif
   decoder fetched from jsDelivr, pinned and checked with Subresource Integrity, without a referrer; the photo itself
   never leaves the page. Strings come from the page ([data-m] elements), so ko/en share this file.
   Output is capped at MAX_PX (phone browsers blank larger canvases): larger pictures are scaled down to fit. */
(function () {
  "use strict";
  var root = document.querySelector('[data-tool="heic-to-jpg"]');
  if (!root || !window.HTMLCanvasElement || !window.Blob || !window.URL) return;
  var $ = function (s) { return root.querySelector(s); };
  var form = $("form"), file = $("#hj-file"), q = $("#hj-q"), status = $("[data-status]"),
      out = $("[data-result]"), body = $("[data-rows]"), drop = $("[data-drop]");
  var MAX_PX = 16777216, MAX_EDGE = 32767, MAX_SRC = 52e6, MAX_FILES = 20;
  var LIB = "https://cdn.jsdelivr.net/npm/libheif-js@1.23.5/libheif-wasm/libheif",
      SRI_JS = "sha384-VEbrgTthZ3xiJrRrD1QszeA+mvSzQAazOjulZBOV9mXAH+SfRdtQWjzL6E0JYlmP",
      SRI_WASM = "sha384-ykFVIusV2Vzqq7NMzIk4GpbFlKHmcCbdhLPI50qMGtV14CpMr+A+5ry6npw4e8z7";
  var lang = document.documentElement.lang === "en" ? "en-US" : "ko-KR";
  var msgs = $("template[data-msgs]").content;
  var files = [], over = false, run = 0, urls = [], chain = Promise.resolve(), heif = null, ready = false;

  function msg(k, v) {
    return msgs.querySelector('[data-m="' + k + '"]').textContent.replace(/\{(\w+)\}/g, function (_, n) { return v[n]; });
  }
  function num(n) { return n.toLocaleString(lang); }
  function size(n) {
    return n < 1e6 ? (n / 1e3).toLocaleString(lang, { maximumFractionDigits: 1 }) + " KB"
                   : (n / 1e6).toLocaleString(lang, { maximumFractionDigits: 2 }) + " MB";
  }
  function say(t, bad) { status.textContent = t; status.classList.toggle("is-error", !!bad); }
  function revoke() { while (urls.length) URL.revokeObjectURL(urls.pop()); }
  function cell(tr, tag, text) {
    var e = document.createElement(tag);
    if (tag === "th") e.scope = "row";
    e.textContent = text; tr.appendChild(e);
    return e;
  }
  function paint() { return new Promise(function (ok) { setTimeout(ok, 30); }); }  // let the status line show

  function decode(f) {  // the browser's own decoder; null when it cannot read the file (HEIC outside Safari)
    return new Promise(function (ok) {
      var u = URL.createObjectURL(f), im = new Image();
      im.onload = function () { ok(im.naturalWidth ? im : null); URL.revokeObjectURL(u); };
      im.onerror = function () { ok(null); URL.revokeObjectURL(u); };
      im.src = u;
    });
  }

  async function isHeif(f) {
    if (/^image\/hei[cf]/i.test(f.type) || /\.(heic|heif|hif)$/i.test(f.name)) return true;
    var b = new Uint8Array(await f.slice(4, 12).arrayBuffer());  // ISO BMFF: size, then ftyp + major brand
    return /^ftyp(hei[cmsx]|hev[cmsx]|mif1|msf1)$/.test(String.fromCharCode.apply(null, b));
  }

  // libheif-js (LGPL-3.0, unmodified, from the CDN): the script, then the wasm, both checked by integrity
  function lib() {
    if (heif) return heif;
    heif = new Promise(function (ok, no) {
      var s = document.createElement("script");
      s.src = LIB + ".js"; s.integrity = SRI_JS; s.crossOrigin = "anonymous"; s.referrerPolicy = "no-referrer";
      s.onload = ok; s.onerror = no; document.head.appendChild(s);
    }).then(function () {
      return fetch(LIB + ".wasm", { integrity: SRI_WASM, credentials: "omit", referrerPolicy: "no-referrer" });
    }).then(function (r) {
      if (!r.ok) throw new Error("wasm " + r.status);
      return r.arrayBuffer();
    }).then(function (buf) {
      return new Promise(function (ok, no) {
        var m = { wasmBinary: buf, onRuntimeInitialized: function () { ready = true; ok(m); }, onAbort: no };
        window.libheif(m);
      });
    });
    heif.catch(function () { heif = null; });  // a failed download is tried again with the next file
    return heif;
  }

  async function viaLib(h, f) {
    var dec = new h.HeifDecoder(), list = dec.decode(new Uint8Array(await f.arrayBuffer()));
    try {
      if (!list.length) return { err: "heic" };
      var im = list.filter(function (x) { return x.is_primary(); })[0] || list[0];  // several pictures: the primary one
      var w = im.get_width(), ht = im.get_height();
      if (w * ht > MAX_SRC) return { err: "big" };
      var id = new ImageData(w, ht);
      if (!(await new Promise(function (ok) { im.display(id, ok); }))) return { err: "heic" };
      return { src: id, w: w, h: ht, n: list.length };
    } finally {
      list.forEach(function (x) { x.free(); });
      if (dec.decoder) { h.heif_context_free(dec.decoder); dec.decoder = null; }
    }
  }

  async function toJpg(src, w, h, quality) {
    var s = Math.min(1, Math.sqrt(MAX_PX / (w * h)), MAX_EDGE / Math.max(w, h)),
        W = Math.max(1, Math.floor(w * s)), H = Math.max(1, Math.floor(h * s)), bm = null,
        cv = document.createElement("canvas");
    try {
      if (src instanceof ImageData)  // drawImage keeps alpha over the white fill; putImageData would not
        bm = await createImageBitmap(src, s < 1 ? { resizeWidth: W, resizeHeight: H, resizeQuality: "high" } : {});
      cv.width = W; cv.height = H;
      var cx = cv.getContext("2d");
      cx.fillStyle = "#fff"; cx.fillRect(0, 0, W, H);  // JPEG has no transparency
      cx.imageSmoothingQuality = "high";
      cx.drawImage(bm || src, 0, 0, W, H);
      var b = await new Promise(function (ok) { cv.toBlob(ok, "image/jpeg", quality); });
      return b && b.type === "image/jpeg" ? { b: b, w: W, h: H, s: s < 1 } : { err: "mem" };
    } catch (e) { return { err: "mem" }; } finally { if (bm) bm.close(); cv.width = cv.height = 0; }
  }

  async function convert(f, quality) {
    var im = await decode(f), r;
    if (im) r = { src: im, w: im.naturalWidth, h: im.naturalHeight, n: 1 };
    else {
      if (!(await isHeif(f))) return { err: "bad" };
      if (!ready) { say(msg("lib")); await paint(); }
      var h;
      try { h = await lib(); } catch (e) { return { err: "net" }; }
      await paint();
      try { r = await viaLib(h, f); } catch (e) { return { err: "mem" }; }
      if (r.err) return r;
    }
    var o = await toJpg(r.src, r.w, r.h, quality);
    o.n = r.n;
    return o;
  }

  // one run at a time: a newer run waits for the file in progress, so only one full-size picture is alive
  function go() {
    var id = ++run;
    revoke(); body.replaceChildren(); out.hidden = true;  // never leave results that do not match the settings
    if (!files.length) { say(msg("none"), true); return; }
    chain = chain.then(function () { if (id === run) return work(id); });
  }

  async function work(id) {
    var quality = +q.value / 100, ok = 0;
    for (var i = 0; i < files.length; i++) {
      say(msg("work", { i: i + 1, n: files.length })); await paint();
      var f = files[i], r = await convert(f, quality);
      if (id !== run) return;  // a newer run took over
      var tr = document.createElement("tr"), name = f.name || "image";
      var th = cell(tr, "th", name.length > 24 ? name.slice(0, 14) + "…" + name.slice(-9) : name);
      th.style.overflowWrap = "anywhere"; th.style.whiteSpace = "normal";
      cell(tr, "td", size(f.size));
      if (r.err) { cell(tr, "td", msg(r.err)); cell(tr, "td", ""); }
      else {
        ok++;
        cell(tr, "td", size(r.b.size) + (r.b.size > f.size ? " " + msg("larger") : ""));
        cell(tr, "td", num(r.w) + " × " + num(r.h) + (r.s ? " " + msg("scaled") : "") + (r.n > 1 ? " " + msg("multi") : ""));
        var u = URL.createObjectURL(r.b), a = document.createElement("a");
        urls.push(u);
        a.className = "button"; a.href = u;
        a.download = (name.replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80) || "image") + ".jpg";
        a.textContent = msg("save"); a.setAttribute("aria-label", msg("save") + ": " + a.download);
        th.appendChild(document.createElement("br")); th.appendChild(a);
      }
      body.appendChild(tr); out.hidden = false;
    }
    say(msg("done", { ok: ok, n: files.length }) + (over ? " " + msg("over") : ""), !ok);
  }

  function take(list) {
    over = list.length > MAX_FILES;
    files = Array.prototype.slice.call(list, 0, MAX_FILES);
    if (files.length) go();
    else { run++; revoke(); body.replaceChildren(); out.hidden = true; say(""); }
  }

  // wiring
  root.querySelectorAll("[data-nojs]").forEach(function (e) { e.remove(); });
  form.hidden = false;
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!files.length && file.files.length) take(file.files); else go();  // the browser may restore the input
  });
  form.addEventListener("change", function (e) {
    if (e.target === file) take(file.files);
    else if (files.length) go();
  });
  q.addEventListener("input", function () { $("[data-q]").textContent = q.value; });
  $("[data-q]").textContent = q.value;
  ["dragenter", "dragover"].forEach(function (n) {
    drop.addEventListener(n, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
  });
  ["dragleave", "drop"].forEach(function (n) {
    drop.addEventListener(n, function (e) { e.preventDefault(); drop.classList.remove("is-over"); });
  });
  drop.addEventListener("drop", function (e) {
    if (!e.dataTransfer || !e.dataTransfer.files.length) return;
    var dropped = Array.prototype.slice.call(e.dataTransfer.files);
    file.value = "";  // so picking the earlier file again fires change
    take(dropped);
  });
})();
