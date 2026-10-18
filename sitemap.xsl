<?xml version="1.0" encoding="UTF-8"?>
<!-- Human view of /sitemap.xml in a browser. Crawlers read the XML and ignore this file. -->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:s="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
  xmlns:xhtml="http://www.w3.org/1999/xhtml" exclude-result-prefixes="s image xhtml">
  <xsl:output method="html" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html lang="ko">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <meta name="robots" content="noindex"/>
        <title>사이트맵 – SugarMount</title>
        <style>
          /* SDS neutral tokens (assets/site.css ref values): paper, white, ink-900, ink-600, line-200, ink-400 link line */
          :root { --bg:#F6F8FB; --fg:#142033; --muted:#4B5668; --line:#DCE2EA; --card:#FFFFFF; --accent:#142033; --link-line:#7C8596; color-scheme:light dark; }
          @media (prefers-color-scheme: dark) { :root { --bg:#0F1622; --fg:#E8EDF4; --muted:#A7B1BF; --line:#2A3546; --card:#172131; --accent:#E8EDF4; --link-line:#6A7487; } }
          * { box-sizing: border-box; }
          body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 system-ui, -apple-system, "Apple SD Gothic Neo", "Noto Sans KR", sans-serif; }
          main { max-width:960px; margin:0 auto; padding:32px 16px 48px; }
          h1 { font-size:24px; margin:0 0 4px; }
          p { color:var(--muted); margin:0 0 20px; }
          .table { background:var(--card); border:1px solid var(--line); border-radius:12px; overflow:hidden; }
          table { width:100%; border-collapse:collapse; }
          th, td { text-align:left; padding:10px 14px; border-bottom:1px solid var(--line); vertical-align:top; }
          th { font-size:13px; color:var(--muted); font-weight:600; }
          tr:last-child td { border-bottom:0; }
          td.url a { color:var(--accent); text-decoration:underline 1px; text-decoration-color:var(--link-line); text-underline-offset:3px; word-break:break-all; }
          td.n { white-space:nowrap; color:var(--muted); font-variant-numeric:tabular-nums; }
          @media (max-width:560px) { th.hide, td.hide { display:none; } }
        </style>
      </head>
      <body>
        <main>
          <h1>사이트맵</h1>
          <p>mvgood21.github.io · 페이지 <xsl:value-of select="count(s:urlset/s:url)"/>개 · 이미지 <xsl:value-of select="count(s:urlset/s:url/image:image)"/>개.
            검색엔진용 XML이며, 사람이 볼 수 있게 표로 보여 줍니다.</p>
          <div class="table">
            <table>
              <tr><th>주소</th><th class="hide">언어</th><th class="hide">이미지</th><th>마지막 수정</th></tr>
              <xsl:for-each select="s:urlset/s:url">
                <tr>
                  <td class="url"><a href="{s:loc}"><xsl:value-of select="substring-after(s:loc, '.io')"/></a></td>
                  <td class="n hide"><xsl:choose><xsl:when test="contains(s:loc, '.io/en/')">en</xsl:when><xsl:otherwise>ko</xsl:otherwise></xsl:choose></td>
                  <td class="n hide"><xsl:value-of select="count(image:image)"/></td>
                  <td class="n"><xsl:value-of select="s:lastmod"/></td>
                </tr>
              </xsl:for-each>
            </table>
          </div>
        </main>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
