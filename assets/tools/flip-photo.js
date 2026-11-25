/* Flip and rotate tool (sugarmount21.com): mirrors or turns photos and keeps their pixel count, in the browser only.
   No upload, no fetch, no libraries. Strings come from the page ([data-m] elements), so ko/en share this file.
   The browser applies the EXIF orientation when it decodes, so a flip follows the way the photo looks.
   JPEG, PNG and WebP keep their format where the browser can write it; HEIC becomes JPEG.
   The file name follows the type the browser really wrote. */
(function () {
  "use strict";
  var root = document.querySelector('[data-tool="flip-photo"]');
  if (!root || !window.HTMLCanvasElement || !window.Blob || !window.URL) return;
  var $ = function (s) { return root.querySelector(s); };
  var form = $("form"), file = $("#fp-file"), status = $("[data-status]"),
      out = $("[data-result]"), body = $("[data-rows]"), drop = $("[data-drop]");
  var MAX_PX = 16777216, MAX_EDGE = 32767, MAX_FILES = 20, THUMB = 88, DPR = 2, QUALITY = 0.95;
  var EXT = { "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp" };
  // op -> canvas matrix (a, b, c, d) around the centre; the 90-degree turns swap width and height
  var OPS = { lr: [-1, 0, 0, 1], ud: [1, 0, 0, -1], half: [-1, 0, 0, -1], right: [0, 1, -1, 0], left: [0, -1, 1, 0] };
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
  function clear() { while (urls.length) URL.revokeObjectURL(urls.pop()); body.replaceChildren(); out.hidden = true; }
  function cell(tr, tag, text) {
    var e = document.createElement(tag);
    if (tag === "th") e.scope = "row";
    e.textContent = text; tr.appendChild(e);
    return e;
  }

  function mime(f) {  // the format to write, "" when the file is not one we read
    if (/hei[cf]/i.test(f.type) || /\.hei[cf]$/i.test(f.name)) return "image/jpeg";
    if (EXT[f.type]) return f.type;
    var m = /^$|\/(jpg|octet-stream)$/i.test(f.type) && /\.(jpe?g|png|webp)$/i.exec(f.name);
    return m ? "image/" + m[1].toLowerCase().replace("jpg", "jpeg") : "";
  }

  function decode(f) {
    return new Promise(function (ok) {
      var u = URL.createObjectURL(f), im = new Image();
      function end(v) { ok(v); URL.revokeObjectURL(u); }
      im.onload = function () {  // decode() rejects what onload lets through, e.g. out of memory
        im.decode().then(function () { end(im.naturalWidth ? im : null); }, function () { end(null); });
      };
      im.onerror = function () { end(null); };
      im.src = u;
    });
  }

  function thumb(cv) {
    var k = Math.min(1, THUMB * DPR / Math.max(cv.width, cv.height)), t = document.createElement("canvas");
    t.width = Math.max(1, Math.round(cv.width * k)); t.height = Math.max(1, Math.round(cv.height * k));
    var x = t.getContext("2d");
    x.imageSmoothingQuality = "high";
    x.drawImage(cv, 0, 0, t.width, t.height);
    t.style.width = Math.max(1, Math.round(t.width / DPR)) + "px";
    return t;
  }

  async function convert(f, op) {
    var type = mime(f);
    if (!type) return { err: "bad" };
    var im = await decode(f);
    if (!im) return { err: /hei[cf]/i.test(f.type) || /\.hei[cf]$/i.test(f.name) ? "heic" : "bad" };
    var w = im.naturalWidth, h = im.naturalHeight, m = OPS[op], turn = m[0] === 0;
    if (w * h > MAX_PX || Math.max(w, h) > MAX_EDGE) return { err: "big" };
    var cv = document.createElement("canvas");
    try {
      var cx = cv.getContext("2d");
      cv.width = turn ? h : w; cv.height = turn ? w : h;
      cx.setTransform(m[0], m[1], m[2], m[3], cv.width / 2, cv.height / 2);
      cx.drawImage(im, -w / 2, -h / 2);
      var b = await new Promise(function (ok) { cv.toBlob(ok, type, QUALITY); });
      if (!b || !EXT[b.type]) return { err: "mem" };
      return { b: b, w: cv.width, h: cv.height, t: thumb(cv) };
    } catch (e) { return { err: "mem" }; } finally { cv.width = cv.height = 0; }
  }

  // one run at a time: a newer run waits for the file in progress, so only one full-size canvas is alive
  function go() {
    var id = ++run;
    clear();  // never leave results that do not match the settings
    if (!files.length) { say(msg("none"), true); return; }
    chain = chain.then(function () { if (id === run) return work(id); }).catch(function () { if (id === run) say(msg("mem"), true); });
  }

  async function work(id) {
    var op = form.querySelector('input[name="fp-op"]:checked').value, ok = 0;
    for (var i = 0; i < files.length; i++) {
      say(msg("work", { i: i + 1, n: files.length }));
      var f = files[i], r = await convert(f, op);
      if (id !== run) return;  // a newer run took over
      var tr = document.createElement("tr"), name = f.name || "photo";
      var th = cell(tr, "th", name.length > 24 ? name.slice(0, 14) + "…" + name.slice(-9) : name);
      th.style.overflowWrap = "anywhere"; th.style.whiteSpace = "normal";
      if (r.err) { cell(tr, "td", msg(r.err)).colSpan = 2; }
      else {
        ok++;
        var u = URL.createObjectURL(r.b), a = document.createElement("a"), td = cell(tr, "td", "");
        urls.push(u);
        r.t.setAttribute("role", "img"); r.t.setAttribute("aria-label", msg("prev") + ": " + name);
        td.appendChild(r.t);
        cell(tr, "td", num(r.w) + " × " + num(r.h) + ", " + size(f.size) + " → " + size(r.b.size));
        a.className = "button"; a.href = u; a.style.whiteSpace = "nowrap";
        a.download = (name.replace(/\.[^.]+$/, "").replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80) || "photo") +
          (op === "lr" || op === "ud" ? "-flip" : "-rotate") + EXT[r.b.type];
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
    else { run++; clear(); say(""); }
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
