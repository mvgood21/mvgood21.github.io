/* PNG to JPG tool (sugarmount21.com): converts PNG/WebP files to JPEG over a chosen background, in the browser only.
   No upload, no fetch, no libraries. Strings come from the page ([data-m] elements), so ko/en share this file.
   Pixel size is kept; an image over MAX_PX fails instead of being shrunk (phone browsers blank larger canvases). */
(function () {
  "use strict";
  var root = document.querySelector('[data-tool="png-to-jpg"]');
  if (!root || !window.HTMLCanvasElement || !window.Blob || !window.URL) return;
  var $ = function (s) { return root.querySelector(s); };
  var form = $("form"), file = $("#pj-file"), q = $("#pj-q"), status = $("[data-status]"),
      out = $("[data-result]"), body = $("[data-rows]"), drop = $("[data-drop]");
  var MAX_PX = 16777216, MAX_EDGE = 32767, MAX_FILES = 20, STRIP = 256;
  var lang = document.documentElement.lang === "en" ? "en-US" : "ko-KR";
  var msgs = $("template[data-msgs]").content;
  var files = [], over = false, run = 0, urls = [], chain = Promise.resolve();

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
  function readable(f) { return /^image\/(png|webp)$/i.test(f.type) || (!f.type && /\.(png|webp)$/i.test(f.name)); }

  function decode(f) {
    return new Promise(function (ok) {
      var u = URL.createObjectURL(f), im = new Image();
      im.onload = function () { ok(im.naturalWidth ? im : null); URL.revokeObjectURL(u); };
      im.onerror = function () { ok(null); URL.revokeObjectURL(u); };
      im.src = u;
    });
  }

  function transparent(cx, w, h) {
    for (var y = 0; y < h; y += STRIP) {
      var d = cx.getImageData(0, y, w, Math.min(STRIP, h - y)).data;
      for (var i = 3; i < d.length; i += 4) if (d[i] < 255) return true;
    }
    return false;
  }

  async function convert(f, bg, quality) {
    if (!readable(f)) return { err: "bad" };
    var im = await decode(f);
    if (!im) return { err: "bad" };
    var w = im.naturalWidth, h = im.naturalHeight;
    if (w * h > MAX_PX || Math.max(w, h) > MAX_EDGE) return { err: "big" };
    var cv = document.createElement("canvas");
    try {
      var cx = cv.getContext("2d", { willReadFrequently: true });
      cv.width = w; cv.height = h;
      cx.drawImage(im, 0, 0);
      var a = transparent(cx, w, h);
      cx.globalCompositeOperation = "destination-over";  // the colour goes under the picture
      cx.fillStyle = bg; cx.fillRect(0, 0, w, h);
      var b = await new Promise(function (ok) { cv.toBlob(ok, "image/jpeg", quality); });
      return b && b.type === "image/jpeg" ? { b: b, w: w, h: h, a: a } : { err: "mem" };
    } catch (e) { return { err: "mem" }; } finally { cv.width = cv.height = 0; }
  }

  // one run at a time: a newer run waits for the file in progress, so only one full-size canvas is alive
  function go() {
    var id = ++run;
    revoke(); body.replaceChildren(); out.hidden = true;  // never leave results that do not match the settings
    if (!files.length) { say(msg("none"), true); return; }
    chain = chain.then(function () { if (id === run) return work(id); });
  }

  async function work(id) {
    var bg = form.querySelector('input[name="pj-bg"]:checked').value, quality = +q.value / 100, ok = 0;
    for (var i = 0; i < files.length; i++) {
      say(msg("work", { i: i + 1, n: files.length }));
      var f = files[i], r = await convert(f, bg, quality);
      if (id !== run) return;  // a newer run took over
      var tr = document.createElement("tr"), name = f.name || "image";
      var th = cell(tr, "th", name.length > 24 ? name.slice(0, 14) + "…" + name.slice(-9) : name);
      th.style.overflowWrap = "anywhere"; th.style.whiteSpace = "normal";
      cell(tr, "td", size(f.size));
      if (r.err) { cell(tr, "td", msg(r.err)); cell(tr, "td", ""); }
      else {
        ok++;
        cell(tr, "td", size(r.b.size) + (r.b.size > f.size ? " " + msg("larger") : ""));
        cell(tr, "td", num(r.w) + " × " + num(r.h) + (r.a ? " " + msg("filled") : ""));
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
