#!/usr/bin/env python3
"""Build the SugarMount site from data/apps.json.

  python3 tools/build.py          # rebuild everything in place
  python3 tools/build.py --check  # exit 1 if a rebuild would change any file

Generated from data:   index.html, en/index.html, apps/index.html, en/apps/index.html (app hub),
                       privacy/index.html, en/privacy/index.html, apps/<app_path>/ for apps with
                       "page": "generated", 404.html, sitemap.xml (index) + sitemap-{main,apps,ax}.xml, rss.xml, en/rss.xml
                       (full <main> per item), robots.txt, llms.txt, /<IndexNow key>.txt, assets/sds-apps.css and
                       assets/fonts/pretendard.css (tools/sds_apps.py), data/content-dates.json (tools/dates.py)
Hand-written pages:    every other *.html keeps its <main> content byte for byte, except the build-owned
                       <!-- build:NAME -->…<!-- /build:NAME --> blocks (tasks, meta, toc, extra, ax-list), which are
                       emptied and refilled on every build. The build replaces <head>, the site header/footer,
                       breadcrumbs and JSON-LD around <main>.
Dates:                 one source, data/content-dates.json (tools/dates.py): a page's modified date changes only when
                       its <main> minus build:* blocks (hand pages) or its input data (generated pages) changes.
Gates:                 --check fails when a rebuild would change a file, when tools/checks.py reports an error over the
                       in-memory outputs, or when an SDS gate fails (contrast, generated tokens, mark colours).
Standard library only.
"""
import hashlib, html, json, math, os, re, sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dates  # noqa: E402
import sds_apps  # noqa: E402  (generated CSS text: assets/sds-apps.css, assets/fonts/pretendard.css)
import checks  # noqa: E402  (site gates run by --check)
import legal_chrome  # noqa: E402  (isolated header/footer for legal pages an app opens; standalone pages)
import ax_extras  # noqa: E402  (AX hub search, note types, inquiry boxes, figures)
import noindex  # noqa: E402  (which pages are noindex)
from html.parser import HTMLParser  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://sugarmount21.com"
EMAIL = "sugarmount21@gmail.com"
PLAY_DEV = "https://play.google.com/store/apps/dev?id=7906745536709395451"
PLAY = "https://play.google.com/store/apps/details?id="
ORG_ID = SITE + "/#org"
SITE_ID = SITE + "/#website"
BRAND = "SugarMount"
SUFFIX = " – SugarMount"
# pages that are noindex: no canonical/og:url/hreflang, and left out of sitemap, RSS and llms.txt (IA spec 2).
# The rule lives in tools/noindex.py (fixed pages, policies, AX lists, data/ax.json "noindex" notes).
NOINDEX_PATHS = noindex.NoIndex()
AX_HUB_LATEST = 6    # newest AX notes on the hub; the rest through search and topic pages (each title costs hub font budget)
ADS = ax_extras.ads_config(ROOT)  # data/ads.json; empty client → no ad markup anywhere
AX_RELATED = 6       # "더 읽기" links under an AX note
RSS_MAX = 60         # newest items per feed (Naver reads the newest; a full-<main> feed grows by 3 notes a day)
TITLE_LEN = {"ko": (30, 44), "en": (50, 65)}  # (topic, whole title), IA spec 3.1

T = {
  "ko": {
    "home": "홈", "crumb_home": BRAND, "apps": "앱", "privacy": "개인정보처리방침", "about": "소개",
    "other_lang": "English", "other_lang_code": "en",
    "skip": "본문으로 건너뛰기", "site_tag": "한 가지 일을 간단하게 하는 Android 앱",
    "home_title": "SugarMount(슈가마운트) – 한 가지 일을 하는 Android 앱",
    "home_desc": "SugarMount는 사진 용량 줄이기, 한글 문서 보기, 맞춤법 검사처럼 한 가지 일을 하는 Android 앱을 만듭니다. 사진·문서 앱은 파일을 기기 안에서 처리합니다.",
    "home_lead": "한 가지 일을 간단하게 하는 Android 앱을 만듭니다. 사진 용량 줄이기부터 한글 문서 보기, 한글 맞춤법, 퍼즐 게임까지 앱마다 하는 일은 하나입니다.",
    "count": "앱 {n}개 중 {live}개를 Google Play에서 받을 수 있습니다.",
    "all_apps": "앱 전체 보기",
    "groups": {"photo": "사진·영상", "video": "사진·영상", "document": "문서·글", "text": "문서·글", "card": "생활", "game": "게임"},
    "group_order": ["사진·영상", "문서·글", "생활", "게임"],
    "status": {"live": "Google Play", "soon": "출시 예정", "review": "심사 중"},
    "get_play": "Google Play에서 받기", "on_play": "Google Play", "policy": "개인정보처리방침",
    "principles_h": "앱을 만드는 원칙",
    # same sentences as /about/ (IA spec 3.2(6)); scope-limited, not site-wide claims
    "principles": [
      ["사진·문서는 기기 안에서", "사진·동영상·문서를 다루는 앱(사진 용량 줄이기, 사진 반전·회전, 이미지 변환, 슈가앨범, 한글뷰어 슈가독)은 파일을 업로드하지 않고 기기에서 처리하며, 원본을 고치거나 지우지 않습니다."],
      ["회원 가입 없이", "공개된 앱 10개 모두 회원 가입이나 로그인 화면이 없습니다. 한글 띄어쓰기는 AI 설명의 하루 이용 횟수를 세려고 이름·이메일과 연결되지 않는 익명 ID를 자동으로 만듭니다."],
      ["구현 그대로의 방침", "앱마다 실제 코드를 기준으로 개인정보처리방침을 쓰고, 광고·통계 SDK가 무엇을 보내는지 적습니다."],
    ],
    "faq_h": "자주 묻는 질문", "about_link": "SugarMount 소개",
    "home_faq": [
      ["SugarMount는 누가 만드나요?", "SugarMount는 개인 개발자 simpest가 Google Play에 앱을 배포할 때 쓰는 개발자 이름입니다. 앱 기획, 개발, 운영을 모두 직접 합니다."],
      ["사진이나 문서가 서버로 올라가나요?", "사진 용량 줄이기, 사진 반전·회전, 이미지 변환, 한글뷰어 슈가독, 슈가앨범은 파일을 업로드하지 않고 기기 안에서만 처리합니다. 한글 띄어쓰기는 검사할 글을 네이버 또는 다음 맞춤법 검사기로 보내 검사합니다. 앱별 자세한 내용은 각 개인정보처리방침에 있습니다."],
      ["앱은 무료인가요?", "모든 앱을 무료로 설치할 수 있습니다. 앱에 따라 광고가 있고, 광고 제거나 Pro 기능을 일회성 구매 또는 구독으로 제공합니다. 한글뷰어 슈가독에는 광고가 없습니다."],
      ["문의나 오류 신고는 어디로 하나요?", "이메일 " + EMAIL + "로 보내 주세요. 앱 이름과 기기 모델, Android 버전을 함께 적어 주시면 빨리 확인할 수 있습니다."],
    ],
    "org_desc": "SugarMount는 개인 개발자 simpest가 Google Play에 앱을 배포할 때 쓰는 개발자 이름입니다.",
    "latest_h": "최신 도움말",
    "contact_h": "문의", "contact_p": "앱 사용 중 문제가 있거나 궁금한 점이 있으면 이메일로 보내 주세요.", "email": "이메일",
    "hub_title": "Android 앱 전체 목록 – SugarMount",
    "hub_desc": "SugarMount가 Google Play에 낸 Android 앱 {n}개를 사진·문서·글·게임 분야별로 모았습니다. 앱마다 소개와 개인정보처리방침이 있습니다.",
    "hub_lead": "SugarMount가 Google Play에 낸 Android 앱입니다. 출시된 앱은 모두 무료로 설치하고 회원 가입 없이 씁니다.",
    "hub_soon_h": "출시 예정", "hub_groups_label": "분야",
    "policy_of": "{name} 개인정보처리방침", "policy_view": "{name} 개인정보처리방침 보기", "play_of": "{name} Google Play에서 받기",
    "privacy_title": "개인정보처리방침 – SugarMount",
    "privacy_desc": "SugarMount가 배포하는 Android 앱의 개인정보처리방침 목록입니다. 앱마다 실제 구현을 기준으로 수집 항목, 처리 주체, 보존과 삭제 방법을 적습니다.",
    "site_policy_h": "웹사이트(sugarmount21.com)", "site_policy_sub": "광고·쿠키와 접속 기록", "site_policy_btn": "웹사이트 방침 보기",
    "privacy_lead": "SugarMount가 배포하는 모든 앱의 개인정보처리방침을 앱별로 안내합니다. 각 방침은 실제 구현을 기준으로 씁니다.",
    "privacy_contact": "개인정보 처리에 관한 문의는 이메일로 보내 주세요.",
    "package": "패키지 이름", "effective": "시행일",
    "axfamily_docs": [["delete", "AXFamily 계정 삭제 요청"], ["terms", "AXFamily 이용약관"]],
    "pol_related_h": "관련 문서", "pol_app": "앱 소개 보기", "pol_guide": "도움말",
    # generated app pages (해요체, like the hand-written app pages)
    "tasks_h": "이런 때 쓰세요", "features_h": "이런 일을 해요", "facts_h": "한눈에 보기", "data_h": "데이터와 권한",
    "limits_h": "할 수 없는 일", "status_h": "상태", "package_h": "패키지 이름", "dev_h": "개발자",
    "privacy_more": "자세한 내용은 {link}에서 볼 수 있어요.",
    "app_contact_p": "앱이 제대로 동작하지 않거나 궁금한 점이 있으면 이메일로 알려 주세요.",
    "related_h": "관련 앱", "shots_label": "{name} 스크린샷", "guides_h": "도움말", "releases_h": "최근 업데이트",
    "updated": "최종 업데이트", "byline": "작성 SugarMount", "read_time": "읽는 시간 {n}분", "toc": "목차",
    "ax": "AX 노트", "ax_nav": "AX 노트", "ax_more": "AX 노트 전체 보기", "ax_related_h": "다른 AX 노트",
    "ax_home_p": "이 앱들을 AI 코딩 에이전트와 함께 만들고 출시하면서 정한 규칙과 실측 숫자를 정리합니다.",
    "footer_apps": "앱", "footer_site": "사이트", "footer_all_apps": "모든 앱", "rss": "RSS 피드",
    "play_dev": "Google Play 개발자 페이지", "copyright": "2026 simpest · SugarMount",
    "main_menu": "주요 메뉴", "full_menu": "전체 메뉴", "menu": "메뉴", "menu_close": "닫기", "menu_all": "모든 앱 보기",
    "nf_title": "페이지를 찾을 수 없습니다 – SugarMount", "nf_h": "페이지를 찾을 수 없습니다", "nf_home": "SugarMount 홈으로",
    "nf_p": "주소가 바뀌었거나 없는 페이지입니다. 홈에서 앱을 찾거나 개인정보처리방침 목록을 확인해 주세요.",
    "og_locale": "ko_KR", "date_fmt": "{y}년 {m}월 {d}일",
  },
  "en": {
    "home": "Home", "crumb_home": BRAND, "apps": "Apps", "privacy": "Privacy policies", "about": "About",
    "other_lang": "한국어", "other_lang_code": "ko",
    "skip": "Skip to content", "site_tag": "Small Android apps that each do one thing simply",
    "home_title": "SugarMount – Small Android apps that each do one thing",
    "home_desc": "SugarMount makes small Android apps that each do one job, from shrinking photos to opening Korean HWP files. Photo and document apps work on the device.",
    "home_lead": "Small Android apps that each do one thing simply, from shrinking photos and opening Korean HWP documents to checking Korean spelling and playing puzzle games.",
    "count": "{live} of {n} apps are on Google Play.",
    "all_apps": "All apps",
    "groups": {"photo": "Photo & video", "video": "Photo & video", "document": "Documents & text", "text": "Documents & text", "card": "Everyday", "game": "Games"},
    "group_order": ["Photo & video", "Documents & text", "Everyday", "Games"],
    "status": {"live": "Google Play", "soon": "Coming soon", "review": "In review"},
    "get_play": "Get it on Google Play", "on_play": "Google Play", "policy": "Privacy policy",
    "principles_h": "How the apps are made",
    "principles": [
      ["Photos and documents stay on the device", "The apps that handle photos, videos and documents (Compress Image, Flip & Rotate Image, Convert Image, SugarAlbum, HWP Viewer SugarDoc) process files on the device without uploading them, and never modify or delete the originals."],
      ["No sign-up", "None of the ten public apps has a sign-up or log-in screen. SugarSpeller creates an anonymous ID, not linked to any name or email, to count daily use of AI explanations."],
      ["Policies that match the code", "Each app's privacy policy is written from its actual code, including what the ad and analytics SDKs send."],
    ],
    "faq_h": "Frequently asked questions", "about_link": "About SugarMount",
    "home_faq": [
      ["Who makes SugarMount apps?", "SugarMount is the developer name used by simpest, an independent developer, to publish apps on Google Play. Planning, development and support are all done by the same person."],
      ["Are my photos or documents uploaded?", "Compress Image, Flip & Rotate Image, Convert Image, HWP Viewer SugarDoc and SugarAlbum process files on your device without uploading them. SugarSpeller sends the text you check to the Naver or Daum spelling checker. Each app's privacy policy has the details."],
      ["Are the apps free?", "All apps are free to install. Some show ads and offer ad removal or Pro features as a one-time purchase or subscription. HWP Viewer SugarDoc has no ads."],
      ["How do I get support or report a bug?", "Email " + EMAIL + ". Including the app name, device model and Android version helps us check faster."],
    ],
    "org_desc": "SugarMount is the developer name used by simpest, an independent developer, to publish apps on Google Play.",
    "latest_h": "Latest help articles",
    "contact_h": "Contact", "contact_p": "If something isn't working or you have a question, send us an email.", "email": "Email",
    "hub_title": "All Android apps – SugarMount",
    "hub_desc": "SugarMount has {n} Android apps on Google Play, grouped by photos, documents, everyday use and games. Each app has an overview page and a privacy policy.",
    "hub_lead": "These are the Android apps SugarMount has published on Google Play, grouped by what they do. Every released app is free to install and works without a sign-up.",
    "hub_soon_h": "Coming soon", "hub_groups_label": "Groups",
    "policy_of": "{name} privacy policy", "policy_view": "Read the {name} privacy policy", "play_of": "Get {name} on Google Play",
    "privacy_title": "Privacy policies – SugarMount",
    "privacy_desc": "Privacy policies for every Android app SugarMount publishes, each written from the app's code: what is collected, who processes it, and how it is deleted.",
    "site_policy_h": "Website (sugarmount21.com)", "site_policy_sub": "Ads, cookies and access logs", "site_policy_btn": "View the website policy",
    "privacy_lead": "Privacy policies for every app SugarMount publishes, one per app, each written from the app's actual implementation.",
    "privacy_contact": "For questions about how your data is handled, email us.",
    "package": "Package name", "effective": "Effective",
    "axfamily_docs": [["delete", "AXFamily account deletion request"], ["terms", "AXFamily terms of service"]],
    "pol_related_h": "Related pages", "pol_app": "About the app", "pol_guide": "Help article",
    "tasks_h": "Use it to", "features_h": "What it does", "facts_h": "At a glance", "data_h": "Data and permissions",
    "limits_h": "What it can't do", "status_h": "Status", "package_h": "Package name", "dev_h": "Developer",
    "privacy_more": "See {link} for details.",
    "app_contact_p": "If something isn't working or you have a question, email us.",
    "related_h": "Related apps", "shots_label": "{name} screenshots", "guides_h": "Help articles", "releases_h": "Recent updates",
    "updated": "Last updated", "byline": "By SugarMount", "read_time": "{n} min read", "toc": "Contents",
    "ax": "AX notes", "ax_nav": "AX notes", "ax_more": "All AX notes", "ax_related_h": "More AX notes",
    "ax_home_p": "How these apps are built and shipped with an AI coding agent: the rules we settled on and the numbers we measured.",
    "footer_apps": "Apps", "footer_site": "Site", "footer_all_apps": "All apps", "rss": "RSS feed",
    "play_dev": "Google Play developer page", "copyright": "2026 simpest · SugarMount",
    "main_menu": "Main menu", "full_menu": "Full menu", "menu": "Menu", "menu_close": "Close", "menu_all": "See all apps",
    "nf_title": "Page not found – SugarMount", "nf_h": "Page not found", "nf_home": "SugarMount home in English",
    "nf_p": "This page has moved or does not exist. Find an app on the home page or check the list of privacy policies.",
    "og_locale": "en_US", "date_fmt": "{M} {d}, {y}",
  },
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
GROUP_IDS = {"사진·영상": "photo", "문서·글": "document", "생활": "everyday", "게임": "games",
             "Photo & video": "photo", "Documents & text": "document", "Everyday": "everyday", "Games": "games"}

def esc(s): return html.escape(s, quote=True)
def rel(path): return os.path.join(ROOT, path)
def read(path):
    with open(rel(path), encoding="utf-8") as f: return f.read()

DATA = json.load(open(rel("data/apps.json"), encoding="utf-8"))
APPS = DATA["apps"]
BY_APP_PATH = {a["app_path"]: a for a in APPS if a.get("app_path")}
BY_PRIVACY_PATH = {a["privacy_path"]: a for a in APPS if a.get("privacy_path")}
BY_PACKAGE = {a["package"]: a for a in APPS}
# AX notes: topic list and each note's topic (data/ax.json); topic pages live at /ax/topic/<id>/
AXD = json.load(open(rel("data/ax.json"), encoding="utf-8"))
# AX topic strings live apart from T: T is part of every generated page's hash input, so new keys there would bump them all
AX_T = {"ko": {"ax_topic_eyebrow": "AX 노트 · 주제", "ax_n": "글 {n}개", "ax_topic_all": "{name} 글 전체 보기", "ax_topic_title": "{name} – AX 노트", "ax_list_h": "글 목록"},
        "en": {"ax_topic_eyebrow": "AX notes · Topic", "ax_n": "{n} notes", "ax_topic_all": "All notes on {name}", "ax_topic_title": "{name} – AX notes", "ax_list_h": "Notes"}}
AX_TOPICS = {tp["id"]: tp for tp in AXD["topics"]}
AX_NOTE_TOPIC = AXD["notes"]
# series (연재): data/ax.json "series": [{id, ko:{name, desc}, en:{name, desc}, slugs:[reading order]}] -> /ax/series/<id>/
AX_SERIES = AXD.get("series", [])
AX_SERIES_OF = {s: (sr, i) for sr in AX_SERIES for i, s in enumerate(sr["slugs"])}
AX_BOARD_PAGE = 20    # rows per board page: the hub is page 1, /ax/page/<n>/ the rest (40 KB HTML budget per page)
AX_RESERVED = {"topic", "series", "page"}  # path segments under /ax/ that are not notes
AX_T["ko"].update({
    "ax_series_eyebrow": "AX 노트 · 연재", "ax_series_title": "{name} – AX 노트 연재", "ax_series_h": "연재",
    "ax_series_badge": "연재 {i}/{n}", "ax_series_n": "{n}편", "ax_series_start": "1편부터 읽기",
    "ax_series_all": "연재 전체 보기", "ax_series_list": "{name} 전체 {n}편", "ax_prev": "이전 편", "ax_next": "다음 편",
    "ax_last": "마지막 편입니다.", "ax_series_nav": "연재 목차", "ax_part": "{i}편",
    "ax_board_h": "글 목록", "ax_board_n": "전체 {n}편", "ax_topics_h": "주제", "ax_pages": "쪽 이동",
    "ax_page_title": "AX 노트 글 목록 {p}쪽", "ax_page_eyebrow": "AX 노트 · 글 목록",
    "ax_page_lead": "AX 노트 전체 글을 최신순으로 {size}편씩 보여 주는 목록입니다. 지금 보는 쪽은 {p}쪽입니다.",
    "ax_page_desc": "SugarMount AX 노트 전체 {n}편 가운데 {a}~{b}번째 글 목록입니다. 주제, 글 유형, 발행일, 연재 순서를 함께 보여 줍니다.",
    "ax_prev_page": "← 새 글", "ax_next_page": "지난 글 →",
})
AX_T["en"].update({
    "ax_series_eyebrow": "AX notes · Series", "ax_series_title": "{name} – AX notes series", "ax_series_h": "Series",
    "ax_series_badge": "Series {i}/{n}", "ax_series_n": "{n} parts", "ax_series_start": "Start with part 1",
    "ax_series_all": "Whole series", "ax_series_list": "{name}: all {n} parts", "ax_prev": "Previous", "ax_next": "Next",
    "ax_last": "This is the last part.", "ax_series_nav": "Series contents", "ax_part": "Part {i}",
    "ax_board_h": "All notes", "ax_board_n": "{n} notes", "ax_topics_h": "Topics", "ax_pages": "Pages",
    "ax_page_title": "AX notes, page {p}", "ax_page_eyebrow": "AX notes · All notes",
    "ax_page_lead": "Every AX note, newest first, {size} to a page. This is page {p} of the list, with each note's topic and date.",
    "ax_page_desc": "Notes {a} to {b} of all {n} SugarMount AX notes, newest first, with each note's topic, note type, publication date and place in a series.",
    "ax_prev_page": "← Newer", "ax_next_page": "Older →",
})

def css_version(generated):
    """One version for all three stylesheets: site.css (committed LF bytes; a Windows checkout with core.autocrlf
    has CRLF and must not change every page) plus the generated CSS texts, computed in memory BEFORE any file is
    written (IA spec 9.1), so two builds in a row change nothing."""
    h = hashlib.sha1(open(rel("assets/site.css"), "rb").read().replace(b"\r\n", b"\n"))
    if exists("assets/ax.css"):  # AX notes' own stylesheet shares the version
        h.update(open(rel("assets/ax.css"), "rb").read().replace(b"\r\n", b"\n"))
    for text in generated:
        h.update(text.encode("utf-8"))
    return h.hexdigest()[:8]
CSSV = "@@CSSV@@"  # placeholder in rendered pages; main() substitutes the real version once the generated CSS exists
CSS_FILES = ("/assets/fonts/pretendard.css", "/assets/site.css", "/assets/sds-apps.css")  # cascade order (SDS 5.2)
# Must equal `python tools/og.py --svg` (og.py draws the same 3-cube mark into favicon, logo and share cards);
# colours come from site.css --sds-mark-* through classes (SDS 6.0.3). --check compares the colours with og.py.
BRAND_MARK = ('<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">'
              '<path class="l" d="M2.14 18 9.07 22 9.07 30 2.14 26Z"/><path class="r" d="M16 18 9.07 22 9.07 30 16 26Z"/>'
              '<path class="t" d="M9.07 14 16 18 9.07 22 2.14 18Z"/>'
              '<path class="e" d="M9.07 14 16 18 16 26 9.07 30 2.14 26 2.14 18Z" fill="none" stroke-width="1.1" stroke-linejoin="round"/>'
              '<path class="l" d="M16 18 22.93 22 22.93 30 16 26Z"/><path class="r" d="M29.86 18 22.93 22 22.93 30 29.86 26Z"/>'
              '<path class="t" d="M22.93 14 29.86 18 22.93 22 16 18Z"/>'
              '<path class="e" d="M22.93 14 29.86 18 29.86 26 22.93 30 16 26 16 18Z" fill="none" stroke-width="1.1" stroke-linejoin="round"/>'
              '<path class="l" d="M9.07 6 16 10 16 18 9.07 14Z"/><path class="r" d="M22.93 6 16 10 16 18 22.93 14Z"/>'
              '<path class="t" d="M16 2 22.93 6 16 10 9.07 6Z"/>'
              '<path class="e" d="M16 2 22.93 6 22.93 14 16 18 9.07 14 9.07 6Z" fill="none" stroke-width="1.1" stroke-linejoin="round"/></svg>')

def other(lang): return "en" if lang == "ko" else "ko"
def prefix(lang): return "/en" if lang == "en" else ""
def url(lang, path):  # path like "/", "/privacy/", "/apps/x/"
    return prefix(lang) + path
def relpath_of(path):  # "/apps/x/" -> "apps/x/index.html", "/404.html" -> "404.html"
    p = path.lstrip("/")
    return p + "index.html" if p == "" or p.endswith("/") else p
def lang_of(relpath): return "en" if relpath.startswith("en/") else "ko"
def bare_of(relpath): return relpath[3:] if relpath.startswith("en/") else relpath
def app_url(a, lang):
    return url(lang, f"/apps/{a['app_path']}/") if a.get("app_path") else None
def privacy_url(a, lang):
    return url(lang, f"/privacy/{a['privacy_path']}/") if a.get("privacy_path") else None
def play_url(a): return PLAY + a["package"] if a.get("play") else None
def play_link(a, lang, medium):
    """Play button URL with an encoded install referrer (IA spec 9.2); JSON-LD keeps the bare play_url()."""
    ref = quote(f"utm_source=sugarmount21.com&utm_medium={medium}&utm_campaign={a['id']}", safe="")
    return f"{play_url(a)}&referrer={ref}" + ("&hl=en" if lang == "en" else "")
def primary_url(a, lang): return app_url(a, lang) or privacy_url(a, lang)
def disp_name(a, lang): return a[lang]["name"]
def full_name(a, lang):
    d = a[lang]
    return d["name"] if d["brand"] in d["name"] else f"{d['name']} ({d['brand']})"
def group_of(a, lang): return T[lang]["groups"][a["category"]]
def live_apps(): return [a for a in APPS if a["status"] == "live"]
def exists(relpath): return os.path.exists(rel(relpath))

def png_size(relpath):
    try:
        with open(rel(relpath), "rb") as f: head_ = f.read(24)
        if head_[:8] == b"\x89PNG\r\n\x1a\n":
            return int.from_bytes(head_[16:20], "big"), int.from_bytes(head_[20:24], "big")
    except OSError:
        pass
    return None

def fit_title(topic, lang):
    """`{topic} – SugarMount`, or the bare topic when the suffix would break the length rule (IA spec 3.1)."""
    t_max, all_max = TITLE_LEN[lang]
    full = topic + SUFFIX
    return full if len(topic) <= t_max and len(full) <= all_max else topic

# ---------------------------------------------------------------- dates (tools/dates.py, IA spec 4.1)
STORE = None          # dates.ContentDates, created in main()
GEN_INPUTS = {}       # relpath -> hash input of a generated page (input data, never rendered HTML)
_DATES = {}

def page_dates(relpath):
    """(published, modified) for a page, from data/content-dates.json after applying the hash rules."""
    if relpath not in _DATES:
        if relpath in GEN_INPUTS:
            hin = GEN_INPUTS[relpath]
        else:
            hin = dates.hand_input(hand_source(relpath))
        _DATES[relpath] = STORE.get(relpath, hin)
    return _DATES[relpath]

def published(relpath): return page_dates(relpath)[0]
def modified(relpath): return page_dates(relpath)[1]

def app_core(a):
    return {k: v for k, v in a.items() if k not in ("ko", "en")}

def generated_inputs():
    """Hash inputs for every generated page: the apps.json fields and T strings it renders, no dates or auto lists."""
    out = {}
    for lang in ("ko", "en"):
        p = "en/" if lang == "en" else ""
        rows = [{"core": app_core(a), "name": a[lang]["name"], "brand": a[lang]["brand"]} for a in APPS]
        out[p + "index.html"] = dates.data_input("home", T[lang], rows)
        out[p + "apps/index.html"] = dates.data_input("hub", T[lang], [dict(r, tagline=a[lang]["tagline"]) for r, a in zip(rows, APPS)])
        out[p + "privacy/index.html"] = dates.data_input(
            "privacy-list", T[lang], [dict(r, effective=effective_date(a, lang) or effective_date(a, "ko")) for r, a in zip(rows, APPS)])
        for a in APPS:
            if a.get("page") == "generated":
                out[f"{p}apps/{a['app_path']}/index.html"] = dates.data_input("app", T[lang], app_core(a), a[lang])
    for relp, (tp, lang) in ax_topic_pages().items():  # a topic page changes when its topic text or its notes change
        out[relp] = dates.data_input("ax-topic", tp[lang], [ax_slug(u) for x, a in ax_by_topic(lang) if x["id"] == tp["id"] for u, _, _ in a])
    for relp, (sr, lang) in ax_series_pages().items():  # a series page changes when its text or its parts change
        out[relp] = dates.data_input("ax-series", sr[lang], [ax_slug(u) for u, _ in ax_series_parts(sr, lang)])
    for relp, (p, lang) in ax_board_page_paths().items():  # a board page changes when its rows change
        rows = ax_articles(lang)[(p - 1) * AX_BOARD_PAGE: p * AX_BOARD_PAGE]
        out[relp] = dates.data_input("ax-page", {"p": p}, [ax_slug(u) for u, _, _ in rows])
    return out

# ---------------------------------------------------------------- shared chrome (SDS 6.1, 6.2; IA 6.1, 6.2, 13)
MENU_SVG = ('<svg viewBox="0 0 18 18" aria-hidden="true"><path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" '
            'stroke-width="1.8" stroke-linecap="round" fill="none"/></svg>')
# optional: close the sheet when focus leaves it (a link behind the sheet must never get focus while hidden, WCAG 2.4.11).
# Without JS: Esc, the close button, the menu button and a click outside still close it (popover="auto").
MENU_JS = ("<script>(function(m){m&&m.addEventListener('focusout',function(e){if(!m.contains(e.relatedTarget)"
           "&&m.matches(':popover-open'))m.hidePopover()})})(document.getElementById('site-menu'))</script>")

def header(lang, current, other_href):
    """Site header: brand, desktop nav, language link, menu button and the Popover menu sheet (server HTML, no JS needed).
    No data-app here: the chrome stays neutral (IA 13 #9); the menu tiles alone carry data-app for their hover colour."""
    t = T[lang]
    cur = lambda k: ' aria-current="page"' if current == k else ""
    groups = []
    for g, apps in grouped(lang, live_apps()):
        gid = "m-" + GROUP_IDS[g]
        tiles = "".join(f'<li><a class="app-tile" data-app="{a["id"]}" href="{primary_url(a, lang)}">{icon_img(a, 48, extra=' loading="lazy"')}'
                        f'<span>{esc(a[lang]["name"])}</span></a></li>' for a in apps)
        groups.append(f'      <p class="menu-title" id="{gid}">{esc(g)}</p>\n'
                      f'      <ul class="app-tiles" aria-labelledby="{gid}">{tiles}</ul>')
    links = "".join(f'<li><a href="{url(lang, p)}"{cur(k)}>{t[label]}</a></li>'
                    for k, p, label in (("ax", "/ax/", "ax_nav"), ("about", "/about/", "about"), ("privacy", "/privacy/", "privacy")))
    return f'''<a class="skip" href="#main">{t["skip"]}</a>
  <header class="site-header">
    <div class="container">
      <a class="brand" href="{url(lang, "/")}">{BRAND_MARK}<span class="brand-name">SugarMount</span></a>
      <nav class="site-nav" aria-label="{t["main_menu"]}">
        <a class="nav-apps" href="{url(lang, "/apps/")}"{cur("apps")}>{t["apps"]}</a>
        <a class="nav-ax" href="{url(lang, "/ax/")}"{cur("ax")}>{t["ax_nav"]}</a>
        <a class="nav-about" href="{url(lang, "/about/")}"{cur("about")}>{t["about"]}</a>
        <a class="nav-privacy" href="{url(lang, "/privacy/")}"{cur("privacy")}>{t["privacy"]}</a>
      </nav>
      <a class="lang" href="{other_href}" lang="{t["other_lang_code"]}" hreflang="{t["other_lang_code"]}">{t["other_lang"]}</a>
      <button class="menu-button" type="button" popovertarget="site-menu">{MENU_SVG}<span>{t["menu"]}</span></button>
    </div>
    <div class="menu" id="site-menu" popover>
      <nav aria-label="{t["full_menu"]}">
      <button class="button button--quiet menu-close" type="button" popovertarget="site-menu" popovertargetaction="hide">{t["menu_close"]}</button>
{chr(10).join(groups)}
      <p><a href="{url(lang, "/apps/")}">{t["menu_all"]}</a></p>
      <ul class="menu-links">{links}</ul>
      </nav>
    </div>
  </header>
  {MENU_JS}'''

def footer(lang):
    """Three blocks (SDS 6.2, IA 6.2): brand + email, live apps in group order, site links. No per-app policy links
    (they would reuse the app name for a second URL, IA 6.4) and no headings outside <main> (p.footer-title)."""
    t = T[lang]
    apps_li = "".join(f'<li><a href="{primary_url(a, lang)}">{esc(disp_name(a, lang))}</a></li>'
                      for _, apps in grouped(lang, live_apps()) for a in apps)
    site_li = "".join(f'<li><a href="{h}">{esc(n)}</a></li>' for h, n in (
        (url(lang, "/apps/"), t["footer_all_apps"]), (url(lang, "/ax/"), t["ax_nav"]), (url(lang, "/about/"), t["about"]),
        (url(lang, "/privacy/"), t["privacy"]), (url(lang, "/sitemap/"), SITEMAP_T[lang]["title"]),
        ("/en/rss.xml" if lang == "en" else "/rss.xml", t["rss"])))
    return f'''<footer class="site-footer">
    <div class="container">
      <div>
        <a class="brand" href="{url(lang, "/")}">{BRAND_MARK}<span>SugarMount</span></a>
        <p>{t["site_tag"]}</p>
        <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
      </div>
      <nav aria-labelledby="f-apps">
        <p class="footer-title" id="f-apps">{t["footer_apps"]}</p>
        <ul>{apps_li}</ul>
      </nav>
      <nav aria-labelledby="f-site">
        <p class="footer-title" id="f-site">{t["footer_site"]}</p>
        <ul>{site_li}</ul>
      </nav>
      <div class="legal"><span><span class="sym">©</span> {t["copyright"]}</span><a href="{PLAY_DEV}" rel="noopener">{t["play_dev"]}</a></div>
    </div>
  </footer>'''

def crumbs(lang, items):
    """items: [(name, href or None)] after the first item; the first item is "SugarMount" on screen and in JSON-LD."""
    t = T[lang]
    allitems = [(t["crumb_home"], url(lang, "/"))] + items
    lis = []
    for i, (name, href) in enumerate(allitems):
        last = i == len(allitems) - 1
        if last or not href:
            lis.append(f'<li><span aria-current="page">{esc(name)}</span></li>' if last else f"<li>{esc(name)}</li>")
        else:
            lis.append(f'<li><a href="{href}">{esc(name)}</a></li>')
    nav = f'<nav class="crumbs" aria-label="{"이동 경로" if lang == "ko" else "Breadcrumb"}"><ol>{"".join(lis)}</ol></nav>'
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": SITE + h} if h else {})} for i, (n, h) in enumerate(allitems)]}
    return nav, ld

ORG_REF = {"@id": ORG_ID}
SITE_REF = {"@id": SITE_ID}

def org_full(lang):
    """The only full Organization node (ko home @graph, /about/ mainEntity). Everything else references ORG_REF."""
    return {"@type": "Organization", "@id": ORG_ID, "name": BRAND, "alternateName": ["슈가마운트"], "url": SITE + "/",
            "logo": {"@type": "ImageObject", "url": SITE + "/assets/logo.png", "width": 512, "height": 512},
            "description": T[lang]["org_desc"], "email": EMAIL,
            "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": EMAIL, "availableLanguage": ["ko", "en"]},
            "sameAs": [PLAY_DEV]}

def app_og(a, lang):
    return f"/assets/og/app-{a['id']}-{lang}.png"

def app_ld(a, lang, page_url, title):
    """@graph: WebPage (primaryImageOfPage = og:image) + MobileApplication (IA spec 5.2)."""
    d = a[lang]
    relp = relpath_of(page_url)
    alt = []
    for x in (d["brand"], d.get("store_title")):
        if x and x != d["name"] and x not in alt: alt.append(x)
    og = app_og(a, lang)
    wp = {"@type": "WebPage", "@id": SITE + page_url, "url": SITE + page_url, "name": title, "inLanguage": lang,
          "isPartOf": SITE_REF, "mainEntity": {"@id": SITE + page_url + "#app"},
          "dateModified": dates.iso_datetime(modified(relp))}
    if exists(og.lstrip("/")):
        w, h = png_size(og.lstrip("/")) or (1200, 630)
        wp["primaryImageOfPage"] = {"@type": "ImageObject", "url": SITE + og, "width": w, "height": h}
    summary = d.get("summary") or clip_sentences(d["desc"], 160)
    app = {"@type": ["MobileApplication", "VideoGame"] if a["category"] == "game" else "MobileApplication",
           "@id": SITE + page_url + "#app", "name": d["name"], "alternateName": alt,
           "description": summary if len(summary) <= 160 else clip_sentences(summary, 160)[:160],
           "url": SITE + page_url,
           # min version from the app repo's minSdk (apps.json min_android); plain "Android" when not verified
           "operatingSystem": (("Android {v} 이상" if lang == "ko" else "Android {v} or later").format(v=a["min_android"])
                               if a.get("min_android") else "Android"),
           "applicationCategory": a["schema_category"], "image": SITE + a["icon"] + ".png"}
    if not alt: del app["alternateName"]
    if a.get("languages"): app["inLanguage"] = a["languages"]
    if d.get("features"): app["featureList"] = [f for f, _ in d["features"]]
    if d.get("shots"):
        app["screenshot"] = [{"@type": "ImageObject", "url": SITE + s["src"], "width": s["w"], "height": s["h"], "caption": s["alt"]}
                             for s in d["shots"] if s.get("w") and s.get("h")]
    if a.get("play"):  # only public listings get an offer and install link
        app["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "KRW"}
        app["installUrl"] = play_url(a); app["sameAs"] = [play_url(a)]
    arts = article_links(lang, a["app_path"]) if a.get("app_path") else []
    if arts: app["softwareHelp"] = [{"@type": "CreativeWork", "name": n, "url": SITE + u} for u, n in arts]
    if d.get("releases"): app["softwareVersion"] = d["releases"][0]["version"]  # shown in "최근 업데이트"
    app["author"] = ORG_REF; app["publisher"] = ORG_REF
    return {"@context": "https://schema.org", "@graph": [wp, app]}

def ld_json(x):
    # "</" inside a script element would end it early
    return json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

def faq_ld(pairs):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": ans}} for q, ans in pairs]}

def head(lang, title, desc, path, alt_path, *, og_type="website", og_image=None, lds=()):
    """<head> (IA spec 3.1, WP-A ③). alt_path is the other language's page path, or None when that file does not exist."""
    t = T[lang]
    relp = relpath_of(path)
    noindex = relp in NOINDEX_PATHS
    canon = SITE + path
    img = og_image if og_image and exists(og_image.lstrip("/")) else "/assets/og.png"
    w, h = png_size(img.lstrip("/")) or (1200, 630)
    lines = ['<meta charset="utf-8">', '<meta name="viewport" content="width=device-width, initial-scale=1">',
             f"<title>{esc(title)}</title>", f'<meta name="description" content="{esc(desc)}">']
    if noindex:
        lines.append('<meta name="robots" content="noindex">')
    else:
        # large image previews in Search and Discover (Google's default is "standard")
        lines.append('<meta name="robots" content="max-image-preview:large">')
        lines.append(f'<link rel="canonical" href="{canon}">')
        if alt_path:
            ko_p, en_p = (path, alt_path) if lang == "ko" else (alt_path, path)
            lines += [f'<link rel="alternate" hreflang="ko" href="{SITE + ko_p}">',
                      f'<link rel="alternate" hreflang="en" href="{SITE + en_p}">',
                      f'<link rel="alternate" hreflang="x-default" href="{SITE + ko_p}">']
    lines += [f'<meta property="og:type" content="{og_type}">', '<meta property="og:site_name" content="SugarMount">',
              f'<meta property="og:title" content="{esc(title)}">', f'<meta property="og:description" content="{esc(desc)}">']
    if not noindex:
        lines.append(f'<meta property="og:url" content="{canon}">')
    lines += [f'<meta property="og:image" content="{SITE + img}">', f'<meta property="og:image:width" content="{w}">',
              f'<meta property="og:image:height" content="{h}">', f'<meta property="og:locale" content="{t["og_locale"]}">']
    if alt_path and not noindex:
        lines.append(f'<meta property="og:locale:alternate" content="{T[other(lang)]["og_locale"]}">')
    feed = "/en/rss.xml" if lang == "en" else "/rss.xml"
    lines += ['<meta name="twitter:card" content="summary_large_image">',
              '<meta name="color-scheme" content="light dark">',
              '<meta name="theme-color" content="#F7FAFE" media="(prefers-color-scheme: light)">',
              '<meta name="theme-color" content="#0E1217" media="(prefers-color-scheme: dark)">',
              # Google Search favicon: square, a multiple of 48 px (favicon.ico has 48); svg for browsers (tools/og.py).
              # assets/favicon.png (96) is still drawn for old links but not linked: the HTML budget is tight on long notes.
              f'<link rel="icon" href="{SITE}/favicon.ico" sizes="48x48">',
              f'<link rel="icon" type="image/svg+xml" href="{SITE}/assets/favicon.svg">',
              f'<link rel="apple-touch-icon" href="{SITE}/assets/apple-touch-icon.png">',  # absolute, like rel=icon (Naver favicon)
              '<link rel="manifest" href="/site.webmanifest">',
              f'<link rel="alternate" type="application/rss+xml" title="SugarMount" href="{SITE}{feed}">']
    if (m := ax_extras.ads_meta(ADS)): lines.append(m)  # AdSense site ownership (data/ads.json client)
    lines += [f'<link rel="stylesheet" href="{c}?v={CSSV}">' for c in CSS_FILES]
    lines += [f'<script type="application/ld+json">{ld_json(x)}</script>' for x in lds]
    return "<head>\n" + "".join(f"  {x}\n" for x in lines) + "</head>"

def page(lang, head_html, body_attrs, header_html, main_html, footer_html, app=None, main_cls=""):
    """main_cls: extra layout class for <main> (e.g. "app-layout": the facts table is a direct child of main, so
    `.app-layout > .facts` can move it to the sticky side column; on <body> it would grid the whole page)."""
    data_app = f' data-app="{app["id"]}"' if app else ""
    return f'''<!DOCTYPE html>
<html lang="{lang}">
{head_html}
<body{body_attrs}>
  {header_html}

  <main id="main" class="container{" " + main_cls if main_cls else ""}"{data_app}>
{main_html}
  </main>

  {footer_html}
</body>
</html>
'''

def icon_img(a, size, cls="app-icon", alt="", extra=""):
    return f'<img class="{cls}" src="{a["icon"]}.webp" width="{size}" height="{size}" alt="{esc(alt)}"{extra}>'

def clip_sentences(text, limit):
    """Keep whole sentences up to limit characters (at least the first sentence)."""
    parts = re.split(r"(?<=[.!?。])\s+", text.strip())
    out = parts[0]
    for p in parts[1:]:
        if len(out) + 1 + len(p) > limit: break
        out += " " + p
    return out

def fmt_date(lang, iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return T[lang]["date_fmt"].format(y=y, m=m, d=d, M=MONTHS[m - 1])

def updated_p(lang, relpath):
    d = modified(relpath)
    return f'<p class="meta updated">{T[lang]["updated"]} <time datetime="{d}">{fmt_date(lang, d)}</time></p>'

def status_p(a, lang, brandline=""):
    b = f' <span class="brandline">{esc(brandline)}</span>' if brandline else ""
    return f'<p class="status"><span class="badge badge--{a["status"]}">{T[lang]["status"][a["status"]]}</span>{b}</p>'

def grouped(lang, apps):
    groups = {}
    for a in apps:
        groups.setdefault(group_of(a, lang), []).append(a)
    return [(g, groups[g]) for g in T[lang]["group_order"] if g in groups]

# ---------------------------------------------------------------- home
def mountain_rows(n):
    rows, k = [], 1
    while n > 0:
        rows.append(min(k, n)); n -= k; k += 1
    return rows

def all_articles(lang):
    """Every help article in this language, newest published first: [(url, h1)]."""
    out = []
    for a in APPS:
        if a.get("app_path"):
            out += [(published(relpath_of(u)), u, n) for u, n in article_links(lang, a["app_path"])]
    out.sort(key=lambda x: x[1]); out.sort(key=lambda x: x[0], reverse=True)
    return [(u, n) for _, u, n in out]

def build_home(lang):
    t = T[lang]
    live = live_apps()
    # the mountain shows only apps people can install, so the rows stay a full triangle (1-2-3-4)
    order = live or APPS
    rows, i, rows_html = mountain_rows(len(order)), 0, []
    for r in rows:
        cells = []
        for a in order[i:i + r]:
            cells.append(f'<a href="{primary_url(a, lang)}" aria-label="{esc(full_name(a, lang))}" style="--i:{i + len(cells)}">{icon_img(a, 84)}</a>')
        rows_html.append(f'        <li class="row">{"".join(cells)}</li>')
        i += r
    group_html = []
    for g, apps in grouped(lang, APPS):
        items = []
        # --sds-vt (not data-app, which belongs on <main> only, IA 13 #9) names the row icon's view transition
        # to the app hero icon on the app page (site.css, motion-guarded)
        for a in apps:
            st = f"\n              {status_p(a, lang)}" if a["status"] != "live" else ""
            items.append(f'''          <li class="app-row" id="{a["id"]}" style="--sds-vt:app-{a["id"]}">
            {icon_img(a, 56)}
            <div>
              <h4 class="app-row-title"><a href="{primary_url(a, lang)}">{esc(a[lang]["name"])}</a></h4>
              <p class="app-row-desc">{esc(a[lang]["tagline"])}</p>{st}
            </div>
          </li>''')
        group_html.append(f'''      <div class="group">
        <h3 class="group-title">{g}</h3>
        <ul class="app-rows">
{chr(10).join(items)}
        </ul>
      </div>''')
    principles = "\n".join(f'      <li><h3>{esc(h)}</h3><p>{esc(p)}</p></li>' for h, p in t["principles"])
    # the first answer ("who makes") links into the entity page /about/ (IA spec 3.2(6), 6.4); anchor differs from the header's
    about_more = f' <a href="{url(lang, "/about/")}">{t["about_link"]}</a>'
    faq = "\n".join(f'      <details><summary>{esc(q)}</summary><div><p>{esc(a_)}{about_more if i == 0 else ""}</p></div></details>'
                    for i, (q, a_) in enumerate(t["home_faq"]))
    latest = all_articles(lang)[:4]
    latest_section = ""
    if latest:
        lis = "\n".join(f'        <li><a href="{u}">{esc(n)}</a></li>' for u, n in latest)
        latest_section = f'''

    <section aria-labelledby="latest-heading">
      <h2 id="latest-heading">{t["latest_h"]}</h2>
      <ul class="related-links">
{lis}
      </ul>
    </section>'''
    # topics, not the newest titles: titles change daily and would move the home page's font subsets (budget 400 KB)
    ax_li = "\n".join(f'        <li><a href="{ax_topic_url(tp, lang)}">{esc(tp[lang]["name"])}</a> '
                      f'<span class="muted">{AX_T[lang]["ax_n"].format(n=len(a))}</span></li>' for tp, a in ax_by_topic(lang))
    ax_section = f'''

    <section aria-labelledby="ax-heading">
      <h2 id="ax-heading"><a href="{url(lang, "/ax/")}">{t["ax"]}</a></h2>
      <p>{t["ax_home_p"]}</p>
      <ul>
{ax_li}
      </ul>
    </section>''' if ax_li else ""
    main = f'''    <section class="home-hero" aria-labelledby="hero-heading">
      <div>
        <h1 id="hero-heading">SugarMount</h1>
        <p class="lead">{t["home_lead"]}</p>
        <p class="actions"><a class="button" href="{url(lang, "/apps/")}">{HOME_CTA[lang][0]}</a> <a class="button button--outline" href="{url(lang, "/ax/")}">{HOME_CTA[lang][1]}</a></p>
        <p class="count">{t["count"].format(n=len(APPS), live=len(live))}</p>
      </div>
      <div>
        <ul class="mountain" aria-label="{t["apps"]}">
{chr(10).join(rows_html)}
        </ul>
        <div class="mountain-base" aria-hidden="true"></div>
      </div>
    </section>

    <section id="apps" aria-labelledby="apps-heading">
      <h2 id="apps-heading">{t["apps"]}</h2>
{chr(10).join(group_html)}
      <p class="more-link"><a href="{url(lang, "/apps/")}">{t["all_apps"]} →</a></p>
    </section>{latest_section}{ax_section}

    <section aria-labelledby="principles-heading">
      <h2 id="principles-heading">{t["principles_h"]}</h2>
      <ul class="principles">
{principles}
      </ul>
    </section>

    <section aria-labelledby="faq-heading">
      <h2 id="faq-heading">{t["faq_h"]}</h2>
      <div class="faq">
{faq}
      </div>
    </section>

    <section aria-labelledby="contact-heading">
      <h2 id="contact-heading">{t["contact_h"]}</h2>
      <p>{t["contact_p"]}</p>
      <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    </section>'''
    path, alt = url(lang, "/"), url(other(lang), "/")
    if lang == "ko":
        graph = [org_full("ko"),
                 {"@type": "WebSite", "@id": SITE_ID, "name": BRAND, "alternateName": ["슈가마운트", "sugarmount21.com"],
                  "url": SITE + "/", "inLanguage": ["ko", "en"], "publisher": ORG_REF}]
    else:
        graph = [{"@type": "WebPage", "@id": SITE + path, "url": SITE + path, "name": t["home_title"], "inLanguage": "en",
                  "isPartOf": SITE_REF, "about": ORG_REF, "dateModified": dates.iso_datetime(modified(relpath_of(path)))}]
    # per-language home card: the ko card carries Korean copy, so /en/ gets its own (tools/og.py home-en)
    h = head(lang, t["home_title"], t["home_desc"], path, alt, og_image="/assets/og.png" if lang == "ko" else "/assets/og/home-en.png",
             lds=[{"@context": "https://schema.org", "@graph": graph}, faq_ld(t["home_faq"])])
    return page(lang, h, "", header(lang, "home", alt), main, footer(lang))

# ---------------------------------------------------------------- app hub /apps/
def build_apps_hub(lang):
    t = T[lang]
    live = live_apps()
    path, alt = url(lang, "/apps/"), url(other(lang), "/apps/")
    nav, bc = crumbs(lang, [(t["apps"], None)])
    groups = grouped(lang, live)
    chips = "".join(f'<li><a href="#{GROUP_IDS[g]}">{esc(g)}</a></li>' for g, _ in groups)
    sections = []
    for g, apps in groups:
        rows = []
        for a in apps:
            d = a[lang]
            links = []
            arts = article_links(lang, a["app_path"]) if a.get("app_path") else []
            arts_html = ""
            if arts:
                arts_html = "\n              <ul class=\"related-links\">" + "".join(
                    f'\n                <li><a href="{u}">{esc(n)}</a></li>' for u, n in arts) + "\n              </ul>"
            links.append(f'<a href="{privacy_url(a, lang)}">{esc(t["policy_of"].format(name=d["name"]))}</a>')
            # Play: the same button as on the app page (a text link here read as a footnote)
            play = (f'\n              <p class="actions"><a class="button button--s play-badge" href="{esc(play_link(a, lang, "hub"))}" '
                    f'rel="noopener">{esc(t["play_of"].format(name=d["name"]))}</a></p>') if a.get("play") else ""
            rows.append(f'''          <li class="app-row" style="--sds-vt:app-{a["id"]}">
            {icon_img(a, 56)}
            <div>
              <h3 class="app-row-title"><a href="{primary_url(a, lang)}">{esc(d["name"])}</a></h3>
              {status_p(a, lang, d["brand"] if d["brand"] != d["name"] else "")}
              <p class="tagline">{esc(d["tagline"])}</p>{arts_html}{play}
              <p class="links">{" · ".join(links)}</p>
            </div>
          </li>''')
        sections.append(f'''    <section class="group" id="{GROUP_IDS[g]}" aria-labelledby="{GROUP_IDS[g]}-h">
      <h2 class="group-title" id="{GROUP_IDS[g]}-h">{esc(g)}</h2>
      <ul class="app-rows">
{chr(10).join(rows)}
      </ul>
    </section>''')
    soon = [a for a in APPS if a["status"] != "live"]
    soon_html = ""
    if soon:
        lis = "\n".join(f'        <li>{esc(a[lang]["name"])} · {esc(a[lang]["tagline"])} · '
                        f'<a href="{privacy_url(a, lang)}">{esc(t["policy_of"].format(name=a[lang]["name"]))}</a></li>' for a in soon)
        soon_html = f'''

    <section aria-labelledby="soon-h">
      <h2 id="soon-h">{t["hub_soon_h"]}</h2>
      <ul>
{lis}
      </ul>
    </section>'''
    main = f'''    {nav}
    <header class="hero">
      <h1>{t["apps"]}</h1>
      <p class="lead">{t["hub_lead"]}</p>
      <ul class="chips" aria-label="{t["hub_groups_label"]}">{chips}</ul>
    </header>

{(chr(10) * 2).join(sections)}{soon_html}

    <section aria-labelledby="contact-heading">
      <h2 id="contact-heading">{t["contact_h"]}</h2>
      <p>{t["contact_p"]}</p>
      <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    </section>'''
    title, desc = t["hub_title"], t["hub_desc"].format(n=len(live))
    lds = [{"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": SITE + path, "url": SITE + path, "name": title, "description": desc, "inLanguage": lang,
         "isPartOf": SITE_REF, "about": ORG_REF, "mainEntity": {"@id": SITE + path + "#apps"},
         "dateModified": dates.iso_datetime(modified(relpath_of(path)))},
        {"@type": "ItemList", "@id": SITE + path + "#apps", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": SITE + app_url(a, lang)} for i, a in enumerate(x for x in live if x.get("app_path"))]},
    ]}, bc]
    h = head(lang, title, desc, path, alt, og_image=f"/assets/og/hub-apps-{lang}.png", lds=lds)
    return page(lang, h, ' class="page-hub"', header(lang, "apps", alt), main, footer(lang))

# ---------------------------------------------------------------- privacy index
def effective_date(a, lang):
    try:
        s = read(f"{'en/' if lang == 'en' else ''}privacy/{a['privacy_path']}/index.html")
    except FileNotFoundError:
        return None
    m = re.search(r"<main[^>]*>(.*)</main>", s, re.S)
    s = m.group(1) if m else s
    if lang == "ko":
        m = re.search(r"시행일[:：]?\s*(?:<[^>]+>\s*)*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", s)
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    m = re.search(r"Effective(?: date)?[:：]?\s*(?:<[^>]+>\s*)*(" + "|".join(MONTHS) + r") (\d{1,2}), (\d{4})", s)
    return f"{int(m.group(3)):04d}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}" if m else None

def build_privacy_index(lang):
    t = T[lang]
    items = []
    for a in APPS:
        if not a.get("privacy_path"): continue
        name = a[lang]["name"]
        eff = effective_date(a, lang) or effective_date(a, "ko")
        eff_s = f' · {t["effective"]} {fmt_date(lang, eff)}' if eff else ""
        subdocs = ""
        if a["privacy_path"] == "axfamily":
            subdocs = "\n          <ul>" + "".join(
                f'<li><a href="{url(lang, f"/privacy/axfamily/{slug}/")}">{esc(label)}</a></li>'
                for slug, label in t["axfamily_docs"] if exists(relpath_of(url(lang, f"/privacy/axfamily/{slug}/")))) + "</ul>"
        items.append(f'''        <li class="card">
          <h2>{esc(full_name(a, lang))}</h2>
          {status_p(a, lang)}
          <p class="sub">{t["package"]} <code>{a["package"]}</code>{eff_s}</p>
          <div class="card-actions"><a class="button button--outline" href="{privacy_url(a, lang)}">{esc(t["policy_view"].format(name=name))}</a></div>{subdocs}
        </li>''')
    if exists(relpath_of(url(lang, "/privacy/site/"))):  # the website's own policy (ads and cookies), first
        items.insert(0, f'''        <li class="card">
          <h2>{t["site_policy_h"]}</h2>
          <p class="sub">{t["site_policy_sub"]}</p>
          <div class="card-actions"><a class="button button--outline" href="{url(lang, "/privacy/site/")}">{t["site_policy_btn"]}</a></div>
        </li>''')
    path, alt = url(lang, "/privacy/"), url(other(lang), "/privacy/")
    nav, bc = crumbs(lang, [(t["privacy"], None)])
    main = f'''    {nav}
    <section class="hero">
      <h1>{t["privacy"]}</h1>
      <p class="lead">{t["privacy_lead"]}</p>
    </section>

    <section aria-label="{t["privacy"]}">
      <ul class="card-list">
{chr(10).join(items)}
      </ul>
    </section>

    <section aria-labelledby="contact-heading">
      <h2 id="contact-heading">{t["contact_h"]}</h2>
      <p>{t["privacy_contact"]}</p>
      <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    </section>'''
    lds = [{"@context": "https://schema.org", "@type": "CollectionPage", "@id": SITE + path, "name": t["privacy_title"], "url": SITE + path,
            "inLanguage": lang, "isPartOf": SITE_REF, "publisher": ORG_REF,
            "dateModified": dates.iso_datetime(modified(relpath_of(path))),
            # the same list the page renders (IA 5.1: CollectionPage + ItemList)
            "mainEntity": {"@type": "ItemList", "@id": SITE + path + "#list", "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": SITE + privacy_url(a, lang)}
                for i, a in enumerate(x for x in APPS if x.get("privacy_path"))]}}, bc]
    h = head(lang, t["privacy_title"], t["privacy_desc"], path, alt, og_image=f"/assets/og/privacy-{lang}.png", lds=lds)
    return page(lang, h, ' class="page-hub"', header(lang, "privacy", alt), main, footer(lang))

# ---------------------------------------------------------------- app page parts shared by generated and hand pages
def tasks_block(a, lang):
    """Inner HTML of <!-- build:tasks -->: "이런 때 쓰세요", a link only when the article file exists (IA spec 3.2(3))."""
    t, rows = T[lang], a[lang].get("tasks") or []
    if not rows: return ""
    lis = []
    for text, slug in rows:
        u = url(lang, f"/apps/{a['app_path']}/{slug}/") if slug else None
        lis.append(f'<li><a href="{u}">{esc(text)}</a></li>' if u and exists(relpath_of(u)) else f"<li>{esc(text)}</li>")
    return (f'\n    <section aria-labelledby="tasks">\n      <h2 id="tasks">{t["tasks_h"]}</h2>\n      <ul>\n'
            + "".join(f"        {x}\n" for x in lis) + "      </ul>\n    </section>\n    ")

def related_apps(a, lang):
    """1-3 live apps: same group first, then other groups in group order, apps.json order inside (IA spec 6.4)."""
    t = T[lang]
    others = [o for o in live_apps() if o is not a and o.get("app_path")]
    same = [o for o in others if group_of(o, lang) == group_of(a, lang)]
    rest = sorted((o for o in others if o not in same), key=lambda o: (t["group_order"].index(group_of(o, lang)), APPS.index(o)))
    return (same + rest)[:3] if len(same) < 2 else same[:3]

def app_extra(a, lang, relpath):
    """Inner HTML of <!-- build:extra --> on an app page: help articles, recent updates, related apps, last updated."""
    t, d = T[lang], a[lang]
    out = []
    arts = article_links(lang, a["app_path"])
    if arts:
        lis = "".join(f'\n        <li><a href="{u}">{esc(n)}</a></li>' for u, n in arts)
        out.append(f'    <section aria-labelledby="guides-heading">\n      <h2 id="guides-heading">{t["guides_h"]}</h2>\n'
                   f'      <ul class="related-links">{lis}\n      </ul>\n    </section>')
    notes = ax_notes_for_app(a, lang)
    if notes:
        lis = "".join(f'\n        <li><a href="{u}">{esc(n)}</a></li>' for u, n, _ in notes)
        out.append(f'    <section aria-labelledby="ax-app-heading">\n      <h2 id="ax-app-heading">{AX_APP_H[lang]}</h2>\n'
                   f'      <ul class="related-links">{lis}\n      </ul>\n    </section>')
    rel_ = d.get("releases") or []
    if rel_:
        lis = "".join(f'\n        <li><strong>{esc(r["version"])}</strong> · <time datetime="{r["date"]}">{fmt_date(lang, r["date"])}</time> · {esc(r["note"])}</li>'
                      for r in rel_[:3])
        out.append(f'    <section aria-labelledby="releases-heading">\n      <h2 id="releases-heading">{t["releases_h"]}</h2>\n'
                   f'      <ul>{lis}\n      </ul>\n    </section>')
    rel_apps = related_apps(a, lang)
    if rel_apps:
        lis = "".join(f'\n        <li><a href="{app_url(o, lang)}">{icon_img(o, 56)}<span>{esc(o[lang]["name"])}</span></a></li>' for o in rel_apps)
        out.append(f'    <section aria-labelledby="related-heading">\n      <h2 id="related-heading">{t["related_h"]}</h2>\n'
                   f'      <ul class="related">{lis}\n      </ul>\n    </section>')
    out.append("    " + updated_p(lang, relpath))
    return "\n" + "\n".join(out) + "\n    "

# ---------------------------------------------------------------- generated app page
def build_app(a, lang):
    t, d = T[lang], a[lang]
    path, alt = app_url(a, lang), app_url(a, other(lang))
    relp = relpath_of(path)
    name = d["name"]
    nav, bc = crumbs(lang, [(t["apps"], url(lang, "/apps/")), (name, None)])
    policy_text = esc(t["policy_of"].format(name=name))
    actions = []
    if a.get("play"): actions.append(f'<a class="button play-badge" href="{esc(play_link(a, lang, "app_page"))}" rel="noopener">{t["get_play"]}</a>')
    actions.append(f'<a class="button button--outline" href="{privacy_url(a, lang)}">{policy_text}</a>')
    shots = "".join(f'<li><img src="{s["src"]}" width="{s["w"]}" height="{s["h"]}" loading="lazy" alt="{esc(s["alt"])}"></li>' for s in d.get("shots", []))
    feats = "\n".join(f'        <li><h3>{esc(h_)}</h3><p>{esc(p)}</p></li>' for h_, p in d.get("features", []))
    facts = [(t["status_h"], esc(t["status"][a["status"]]))] + [(k, esc(v)) for k, v in d.get("facts", [])] + \
            [(t["package_h"], f'<code>{a["package"]}</code>'), (t["dev_h"], "simpest (SugarMount)")]
    facts_html = "\n".join(f'            <tr><th scope="row">{esc(k)}</th><td>{v}</td></tr>' for k, v in facts)
    priv = "\n".join(f"        <li>{esc(x)}</li>" for x in d.get("privacy", []))
    limits = "\n".join(f"        <li>{esc(x)}</li>" for x in d.get("limits", []))
    policy_link = f'<a href="{privacy_url(a, lang)}">{policy_text}</a>'
    faq = "\n".join(f'        <details><summary>{esc(q)}</summary><div><p>{esc(x)}</p></div></details>' for q, x in d.get("faq", []))
    brandline = " · ".join(x for x in [d["brand"] if d["brand"] != name else "", d.get("store_title") or ""] if x and x != name)
    lead = d.get("summary") or clip_sentences(d["desc"], 90 if lang == "ko" else 300)
    limits_section = f'''

    <section aria-labelledby="limits">
      <h2 id="limits">{t["limits_h"]}</h2>
      <ul>
{limits}
      </ul>
    </section>''' if limits else ""
    faq_section = f'''

    <section aria-labelledby="faq">
      <h2 id="faq">{t["faq_h"]}</h2>
      <div class="faq">
{faq}
      </div>
    </section>''' if faq else ""
    main = f'''    {nav}
    <header class="app-hero">
      {icon_img(a, 96, extra=' fetchpriority="high"')}
      <h1>{esc(name)}</h1>
      <p class="lead">{esc(lead)}</p>
      {status_p(a, lang, brandline)}
      <div class="actions">{"".join(actions)}</div>
    </header>

    {f'<ul class="shots" tabindex="0" aria-label="{esc(t["shots_label"].format(name=name))}">{shots}</ul>' if shots else ''}

    <!-- build:tasks -->{tasks_block(a, lang)}<!-- /build:tasks -->

    <section aria-labelledby="features">
      <h2 id="features">{t["features_h"]}</h2>
      <ul class="features">
{feats}
      </ul>
    </section>

    <section class="facts" aria-labelledby="facts-h">
      <h2 id="facts-h">{t["facts_h"]}</h2>
      <div class="table-wrap">
        <table>
          <tbody>
{facts_html}
          </tbody>
        </table>
      </div>
    </section>

    <section aria-labelledby="data">
      <h2 id="data">{t["data_h"]}</h2>
      <ul>
{priv}
      </ul>
      <p>{t["privacy_more"].format(link=policy_link)}</p>
    </section>{limits_section}{faq_section}

    <!-- build:extra -->{app_extra(a, lang, relp)}<!-- /build:extra -->

    <section aria-labelledby="contact">
      <h2 id="contact">{t["contact_h"]}</h2>
      <p>{t["app_contact_p"]}</p>
      <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a> · {t["package_h"]}: <code>{a["package"]}</code></p>
    </section>'''
    title = fit_title(d["title_topic"], lang) if d.get("title_topic") else fit_title(name, lang)
    desc = d.get("meta") or clip_sentences(d["desc"], 110 if lang == "ko" else 160)
    lds = [app_ld(a, lang, path, title), bc]
    if d.get("faq"): lds.append(faq_ld(d["faq"]))
    h = head(lang, title, desc, path, alt, og_image=app_og(a, lang), lds=lds)
    return page(lang, h, "", header(lang, "apps", alt), main, footer(lang), app=a, main_cls="app-layout")

# ---------------------------------------------------------------- hand-written pages
def plain(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()

def h1_text(s):
    mh = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    return plain(mh.group(1)) if mh else None

def article_links(lang, app_path):
    """Help articles under apps/<app_path>/<slug>/ in this language, newest published first: [(url, h1)]."""
    base = rel(("en/" if lang == "en" else "") + f"apps/{app_path}")
    out = []
    if os.path.isdir(base):
        for slug in sorted(os.listdir(base)):
            f = os.path.join(base, slug, "index.html")
            if not os.path.isfile(f): continue
            relp = os.path.relpath(f, ROOT).replace(os.sep, "/")
            out.append((published(relp), "/" + relp[:-len("index.html")], h1_text(read(relp)) or slug))
    out.sort(key=lambda x: x[1]); out.sort(key=lambda x: x[0], reverse=True)
    return [(u, n) for _, u, n in out]

def ax_articles(lang):
    """AX notes under ax/<slug>/ in this language: [(url, h1, description)], newest published first, then by slug."""
    base = rel(("en/" if lang == "en" else "") + "ax")
    out = []
    if os.path.isdir(base):
        for slug in os.listdir(base):
            f = os.path.join(base, slug, "index.html")
            if slug in AX_RESERVED or not os.path.isfile(f): continue
            relp = os.path.relpath(f, ROOT).replace(os.sep, "/")
            s = read(relp)
            md = re.search(r'<meta name="description" content="([^"]*)"', s)
            out.append((published(relp), slug, "/" + relp[:-len("index.html")], h1_text(s) or slug,
                        html.unescape(md.group(1)) if md else ""))
    out.sort(key=lambda x: x[1]); out.sort(key=lambda x: x[0], reverse=True)
    return [(u, n, d) for _, _, u, n, d in out]

AX_APP_H = {"ko": "이 앱의 AX 노트", "en": "AX notes on this app"}  # kept out of T so a new key does not re-date every generated page
# home hero entry points (2026-11-13 rebrand): apps and AX notes; out of T for the same reason
HOME_CTA = {"ko": ("앱 둘러보기", "AX 노트 읽기"), "en": ("Browse apps", "Read AX notes")}

def ax_notes_for_app(a, lang, limit=3):
    """Newest AX notes whose hand-written body links this app's page (build blocks and site menus ignored)."""
    target = app_url(a, lang)
    if not target: return []
    out = []
    for u, n, d in ax_articles(lang):
        m = re.search(r"<main.*?</main>", read(relpath_of(u)), re.S)
        body = re.sub(r"<!-- build:([\w-]+) -->.*?<!-- /build:\1 -->", "", m.group(0), flags=re.S) if m else ""
        if f'href="{target}"' in body: out.append((u, n, d))
        if len(out) == limit: break
    return out

def ax_slug(u): return u.rstrip("/").rsplit("/", 1)[-1]
def ax_topic_of(u): return AX_TOPICS.get(AX_NOTE_TOPIC.get(ax_slug(u)))
def ax_topic_url(tp, lang): return url(lang, f"/ax/topic/{tp['id']}/")
def ax_type(u): return ax_extras.note_type(read(relpath_of(u)), "")
def ax_label(u, lang):
    """'Android 개발 · 사고 기록 · 2026년 10월 22일': topic, note type, published date (hub cards, search)."""
    tp = ax_topic_of(u)
    return " · ".join(x for x in (tp[lang]["name"] if tp else "", ax_type(u), fmt_date(lang, published(relpath_of(u)))) if x)

def ax_by_topic(lang):
    """[(topic, [(url, h1, description)])] in data/ax.json order, newest first inside a topic; empty topics left out."""
    arts = ax_articles(lang)
    out = []
    for tp in AXD["topics"]:
        mine = [x for x in arts if AX_NOTE_TOPIC.get(ax_slug(x[0])) == tp["id"]]
        if mine: out.append((tp, mine))
    return out

def ax_cards(arts, indent="      "):
    return "".join(f'\n{indent}  <li class="card"><h3><a href="{u}">{esc(n)}</a></h3><p class="sub">{esc(d)}</p></li>' for u, n, d in arts)

def ax_topic_pages():
    """relpaths of the topic pages to generate: one per topic that has at least one note in that language."""
    return {("en/" if lang == "en" else "") + f"ax/topic/{tp['id']}/index.html": (tp, lang)
            for lang in ("ko", "en") for tp, _ in ax_by_topic(lang)}

def build_ax_topic(tp, lang):
    t = T[lang]
    d = tp[lang]
    arts = next(a for x, a in ax_by_topic(lang) if x["id"] == tp["id"])
    path = ax_topic_url(tp, lang)
    alt_p = ax_topic_url(tp, other(lang))
    alt = alt_p if any(x["id"] == tp["id"] for x, _ in ax_by_topic(other(lang))) else None
    nav, bc = crumbs(lang, [(t["ax"], url(lang, "/ax/")), (d["name"], None)])
    others = [(x, a) for x, a in ax_by_topic(lang) if x["id"] != tp["id"]]
    chips = "".join(f'<li><a href="{ax_topic_url(x, lang)}">{esc(x[lang]["name"])}</a></li>' for x, _ in others)
    chips_html = f'\n      <ul class="chips" aria-label="{t["ax"]}">{chips}</ul>' if chips else ""
    main = f'''    {nav}
    <header class="hero">
      <span class="eyebrow">{AX_T[lang]["ax_topic_eyebrow"]}</span>
      <h1>{esc(d["name"])}</h1>
      <p class="lead">{esc(d["desc"])}</p>
      <p class="meta">{AX_T[lang]["ax_n"].format(n=len(arts))}</p>{chips_html}
    </header>

    <section aria-labelledby="notes-h">
      <h2 id="notes-h">{AX_T[lang]["ax_list_h"]}</h2>
      <ul class="card-list">{ax_cards(arts, "      ")}
      </ul>
      <p><a href="{url(lang, "/ax/")}">{t["ax_more"]}</a></p>
    </section>'''
    title = fit_title(AX_T[lang]["ax_topic_title"].format(name=d["name"]), lang)
    relp = relpath_of(path)
    lds = [{"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": SITE + path, "url": SITE + path, "name": title, "description": d["desc"], "inLanguage": lang,
         "isPartOf": SITE_REF, "publisher": ORG_REF, "mainEntity": {"@id": SITE + path + "#list"},
         "dateModified": dates.iso_datetime(modified(relp))},
        {"@type": "ItemList", "@id": SITE + path + "#list", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": SITE + u} for i, (u, _, _) in enumerate(arts)]},
    ]}, bc]
    h = head(lang, title, d["desc"], path, alt, og_image=f"/assets/og/ax-{lang}.png", lds=lds)
    return page(lang, h, ' class="page-hub"', header(lang, "ax", alt or url(other(lang), "/ax/")), main, footer(lang))

# ---------------------------------------------------------------- AX board and series (2026-11-13 hub redesign)
SEP = ' <span aria-hidden="true">·</span> '

def ax_series_url(sr, lang): return url(lang, f"/ax/series/{sr['id']}/")
def ax_page_url(p, lang): return url(lang, "/ax/") if p == 1 else url(lang, f"/ax/page/{p}/")

def ax_series_parts(sr, lang):
    """[(url, h1)] of a series' notes that exist in this language, in reading order."""
    by = {ax_slug(u): (u, n) for u, n, _ in ax_articles(lang)}
    return [by[s] for s in sr["slugs"] if s in by]

def ax_series_pos(slug, lang):
    """(series, index, parts) when the note is in a series in this language, else None."""
    hit = AX_SERIES_OF.get(slug)
    if not hit: return None
    parts = ax_series_parts(hit[0], lang)
    idx = next((i for i, (u, _) in enumerate(parts) if ax_slug(u) == slug), None)
    return (hit[0], idx, parts) if idx is not None else None

def ax_row(u, n, d, lang, desc=True):
    """Board row (2 lines): title / topic · type · date · series badge, then a one-line summary."""
    tp = ax_topic_of(u)
    pub = published(relpath_of(u))
    bits = []
    if tp: bits.append(f'<a class="ax-tag" href="{ax_topic_url(tp, lang)}">{esc(tp[lang]["name"])}</a>')
    ty = ax_type(u)
    if ty: bits.append(f"<span>{esc(ty)}</span>")
    bits.append(f'<time datetime="{pub}">{fmt_date(lang, pub)}</time>')
    pos = ax_series_pos(ax_slug(u), lang)
    if pos:
        sr, i, parts = pos
        bits.append(f'<span class="ax-tag ax-tag-series" title="{esc(sr[lang]["name"])}">'
                    f'{esc(AX_T[lang]["ax_series_badge"].format(i=i + 1, n=len(parts)))}</span>')
    sub = f'<p class="ax-row-desc">{esc(clip_sentences(d, 90 if lang == "ko" else 150))}</p>' if desc and d else ""
    return f'\n        <li><a class="ax-row-title" href="{u}">{esc(n)}</a><p class="ax-row-meta">{SEP.join(bits)}</p>{sub}</li>'

def ax_board_pages(lang):
    arts = ax_articles(lang)
    return max(1, math.ceil(len(arts) / AX_BOARD_PAGE))

def ax_pager(p, lang):
    n = ax_board_pages(lang)
    if n == 1: return ""
    t = AX_T[lang]
    links = []
    if p > 1: links.append(f'<a href="{ax_page_url(p - 1, lang)}" rel="prev">{t["ax_prev_page"]}</a>')
    for k in range(1, n + 1):
        links.append(f'<a aria-current="page" href="{ax_page_url(k, lang)}">{k}</a>' if k == p
                     else f'<a href="{ax_page_url(k, lang)}">{k}</a>')
    if p < n: links.append(f'<a href="{ax_page_url(p + 1, lang)}" rel="next">{t["ax_next_page"]}</a>')
    return f'\n      <nav class="ax-pager" aria-label="{t["ax_pages"]}">{"".join(links)}</nav>'

def ax_board(p, lang):
    """Board page p (1 = the hub): AX_BOARD_PAGE rows, newest first, then the pager."""
    arts = ax_articles(lang)
    rows = arts[(p - 1) * AX_BOARD_PAGE: p * AX_BOARD_PAGE]
    return f'\n      <ul class="ax-board">{"".join(ax_row(u, n, d, lang) for u, n, d in rows)}\n      </ul>{ax_pager(p, lang)}\n      ', rows

def ax_series_cards(lang):
    t = AX_T[lang]
    out = []
    for sr in AX_SERIES:
        parts = ax_series_parts(sr, lang)
        if not parts: continue
        last = max(published(relpath_of(u)) for u, _ in parts)
        out.append(f'\n        <li class="ax-series-card"><a class="ax-row-title" href="{ax_series_url(sr, lang)}">{esc(sr[lang]["name"])}</a>'
                   f'<p class="ax-row-desc">{esc(sr[lang]["desc"])}</p>'
                   f'<p class="ax-row-meta"><span>{t["ax_series_n"].format(n=len(parts))}</span>{SEP}'
                   f'<time datetime="{last}">{fmt_date(lang, last)}</time></p></li>')
    return f'\n      <ul class="ax-series-grid">{"".join(out)}\n      </ul>\n      ' if out else ""

def ax_topic_chips(lang, current=None):
    cur = ' aria-current="page"'
    lis = "".join(f'<li><a href="{ax_topic_url(tp, lang)}"{cur if tp["id"] == current else ""}>'
                  f'{esc(tp[lang]["name"])} <span class="n">{len(a)}</span></a></li>' for tp, a in ax_by_topic(lang))
    return f'\n      <ul class="chips ax-chips">{lis}</ul>\n      '

def ax_series_top(slug, lang):
    """Line under the meta of a series note: 'series name i/n', linking the series page (prev/next sit in the end box)."""
    pos = ax_series_pos(slug, lang)
    if not pos: return ""
    sr, i, parts = pos
    t = AX_T[lang]
    bits = [f'<a href="{ax_series_url(sr, lang)}">{esc(sr[lang]["name"])}</a> {i + 1}/{len(parts)}']
    return '<p class="note ax-series-line">' + bits[0] + "</p>"

def ax_series_nav(slug, lang):
    """Box at the end of a series note: the series page, then the previous and next parts (the full list is the series
    page; the current title is not repeated: every byte counts against the 40 KB page budget)."""
    pos = ax_series_pos(slug, lang)
    if not pos: return ""
    sr, i, parts = pos
    t = AX_T[lang]
    near = [k for k in (i - 1, i + 1) if 0 <= k < len(parts)]
    lis = "".join(f'<li value="{k + 1}"><a href="{parts[k][0]}">{esc(parts[k][1])}</a></li>' for k in near)
    nxt = "" if i < len(parts) - 1 else f'<p>{t["ax_last"]}</p>'
    return (f'\n    <nav class="box ax-series-box" aria-label="{t["ax_series_nav"]}"><p><strong>'
            f'<a href="{ax_series_url(sr, lang)}">{esc(t["ax_series_list"].format(name=sr[lang]["name"], n=len(parts)))}</a>'
            f'</strong></p><ol>{lis}</ol>{nxt}</nav>\n    ')

def ax_series_pages():
    return {("en/" if lang == "en" else "") + f"ax/series/{sr['id']}/index.html": (sr, lang)
            for lang in ("ko", "en") for sr in AX_SERIES if ax_series_parts(sr, lang)}

def ax_board_page_paths():
    return {("en/" if lang == "en" else "") + f"ax/page/{p}/index.html": (p, lang)
            for lang in ("ko", "en") for p in range(2, ax_board_pages(lang) + 1)}

def ax_css(h):
    return h.replace("</head>", f'  <link rel="stylesheet" href="/assets/ax.css?v={CSSV}">\n</head>')

def build_ax_series(sr, lang):
    t, at = T[lang], AX_T[lang]
    d = sr[lang]
    parts = ax_series_parts(sr, lang)
    path = ax_series_url(sr, lang)
    alt = ax_series_url(sr, other(lang)) if ax_series_parts(sr, other(lang)) else None
    nav, bc = crumbs(lang, [(t["ax"], url(lang, "/ax/")), (at["ax_series_h"], url(lang, "/ax/") + "#series"), (d["name"], None)])
    descs = {u: dd for u, _, dd in ax_articles(lang)}
    rows = "".join(
        f'\n        <li><span class="ax-part">{at["ax_part"].format(i=i + 1)}</span><a class="ax-row-title" href="{u}">{esc(n)}</a>'
        f'<p class="ax-row-meta"><time datetime="{published(relpath_of(u))}">{fmt_date(lang, published(relpath_of(u)))}</time></p>'
        f'<p class="ax-row-desc">{esc(clip_sentences(descs.get(u, ""), 90 if lang == "ko" else 150))}</p></li>'
        for i, (u, n) in enumerate(parts))
    main = f'''    {nav}
    <header class="hero">
      <span class="eyebrow">{at["ax_series_eyebrow"]}</span>
      <h1>{esc(d["name"])}</h1>
      <p class="lead">{esc(d["desc"])}</p>
      <p class="meta">{at["ax_series_n"].format(n=len(parts))}</p>
    </header>

    <section aria-labelledby="parts-h">
      <h2 id="parts-h">{at["ax_series_nav"]}</h2>
      <ol class="ax-board ax-series-list">{rows}
      </ol>
      <p><a href="{url(lang, "/ax/")}">{t["ax_more"]}</a></p>
    </section>'''
    title = fit_title(at["ax_series_title"].format(name=d["name"]), lang)
    relp = relpath_of(path)
    lds = [{"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": SITE + path, "url": SITE + path, "name": title, "description": d["desc"], "inLanguage": lang,
         "isPartOf": SITE_REF, "publisher": ORG_REF, "mainEntity": {"@id": SITE + path + "#list"},
         "dateModified": dates.iso_datetime(modified(relp))},
        {"@type": "ItemList", "@id": SITE + path + "#list", "itemListOrder": "https://schema.org/ItemListOrderAscending",
         "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + u} for i, (u, _) in enumerate(parts)]},
    ]}, bc]
    h = ax_css(head(lang, title, d["desc"], path, alt, og_image=f"/assets/og/ax-{lang}.png", lds=lds))
    return page(lang, h, ' class="page-hub"', header(lang, "ax", alt or url(other(lang), "/ax/")), main, footer(lang))

def build_ax_page(p, lang):
    t, at = T[lang], AX_T[lang]
    total = len(ax_articles(lang))
    board, rows = ax_board(p, lang)
    path = ax_page_url(p, lang)
    alt = ax_page_url(p, other(lang)) if p <= ax_board_pages(other(lang)) else None
    nav, bc = crumbs(lang, [(t["ax"], url(lang, "/ax/")), (at["ax_page_title"].format(p=p), None)])
    a, b = (p - 1) * AX_BOARD_PAGE + 1, (p - 1) * AX_BOARD_PAGE + len(rows)
    desc = at["ax_page_desc"].format(n=total, a=a, b=b)
    main = f'''    {nav}
    <header class="hero">
      <span class="eyebrow">{at["ax_page_eyebrow"]}</span>
      <h1>{at["ax_page_title"].format(p=p)}</h1>
      <p class="lead">{at["ax_page_lead"].format(size=AX_BOARD_PAGE, p=p)}</p>
      <p class="meta">{at["ax_board_n"].format(n=total)}</p>
    </header>

    <section aria-labelledby="board-h">
      <h2 id="board-h">{at["ax_board_h"]}</h2>{board}
    </section>'''
    title = fit_title(at["ax_page_title"].format(p=p), lang)
    relp = relpath_of(path)
    lds = [{"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "@id": SITE + path, "url": SITE + path, "name": title, "description": desc, "inLanguage": lang,
         "isPartOf": SITE_REF, "publisher": ORG_REF, "mainEntity": {"@id": SITE + path + "#list"},
         "dateModified": dates.iso_datetime(modified(relp))},
        {"@type": "ItemList", "@id": SITE + path + "#list", "itemListElement": [
            {"@type": "ListItem", "position": a + i, "url": SITE + u} for i, (u, _, _) in enumerate(rows)]},
    ]}, bc]
    h = ax_css(head(lang, title, desc, path, alt, og_image=f"/assets/og/ax-{lang}.png", lds=lds))
    return page(lang, h, ' class="page-hub"', header(lang, "ax", alt or url(other(lang), "/ax/")), main, footer(lang))

BLOCK_RE = lambda name: re.compile(r"<!-- build:" + name + r" -->.*?<!-- /build:" + name + r" -->", re.S)

def set_block(main, name, inner, insert_at=None):
    """Fill <!-- build:NAME --> in place when the hand file has the marker; otherwise insert it at insert_at (or append)."""
    block = f"<!-- build:{name} -->{inner}<!-- /build:{name} -->"
    if BLOCK_RE(name).search(main):
        return BLOCK_RE(name).sub(lambda _: block, main, count=1)
    if insert_at is None:
        return main.rstrip() + "\n\n    " + block
    return main[:insert_at] + "\n\n    " + block + main[insert_at:]

def after_lead(main):
    """Offset just after the <p class="lead"> that follows the H1 (or after the H1)."""
    mh = re.search(r"<h1\b[^>]*>.*?</h1>", main, re.S)
    if not mh: return None
    ml = re.compile(r'\s*<p class="lead"[^>]*>.*?</p>', re.S).match(main, mh.end())
    return ml.end() if ml else mh.end()

def after_hero(main):
    """Offset just after the hero block that holds the H1, or after the lead when the H1 is not in one."""
    mh = re.search(r"<h1\b", main)
    if not mh: return None
    heroes = [m for m in re.finditer(r'<(section|header|div)\b[^>]*class="(?:app-)?hero\b[^"]*"[^>]*>', main) if m.start() < mh.start()]
    if heroes:
        tag = heroes[-1].group(1)
        close = main.find(f"</{tag}>", mh.start())
        if close != -1: return close + len(f"</{tag}>")
    return after_lead(main)

def reading_minutes(main, lang):
    text = plain(dates.strip_build_blocks(re.sub(r'<nav class="crumbs".*?</nav>', "", main, flags=re.S)))
    if lang == "en":
        return max(1, math.ceil(len(text.split()) / 230))
    return max(1, math.ceil(len(re.sub(r"\s", "", text)) / 500))

def meta_line(lang, relpath, main, category=None):
    t = T[lang]
    d = modified(relpath)
    sep = ' <span aria-hidden="true">·</span> '
    parts = [f'<a href="{url(lang, "/about/")}">{t["byline"]}</a>']
    if category: parts.append(f"<span>{esc(category)}</span>")
    parts.append(f'<span>{t["read_time"].format(n=reading_minutes(main, lang))}</span>')
    parts.append(f'{t["updated"]} <time datetime="{d}">{fmt_date(lang, d)}</time>')
    return f'<p class="meta">{sep.join(parts)}</p>'

def toc_inner(main, lang):
    """Inner HTML of <!-- build:toc --> from h2[id] outside build blocks; empty below 3 headings (SDS 6.16)."""
    body = dates.strip_build_blocks(main)
    hs = [(m.group(1), plain(m.group(2))) for m in re.finditer(r'<h2\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</h2>', body, re.S)]
    if len(hs) < 3: return ""
    t = T[lang]
    ol = "<ol>" + "".join(f'<li><a href="#{i}">{esc(n)}</a></li>' for i, n in hs) + "</ol>"
    return (f'<details class="toc-inline"><summary>{t["toc"]} ({len(hs)})</summary>{ol}</details>'
            f'<nav class="toc" aria-labelledby="toc-h"><p id="toc-h" class="toc-title">{t["toc"]}</p>{ol}</nav>')

def article_images(a, slug, lang):
    """Article image set (16:9, 4:3, 1:1) made by tools/og.py; the 16:9 one is og:image."""
    return [f"/assets/og/article-{a['id']}-{slug}-{r}-{lang}.png" for r in ("16x9", "4x3", "1x1")
            if exists(f"assets/og/article-{a['id']}-{slug}-{r}-{lang}.png")]

PLAY_HREF_RE = re.compile(r'href="https://play\.google\.com/store/apps/details\?id=([\w.]+)[^"]*"')

def hand_source(relpath):
    """A hand-written file as the build reads it. The one rewrite: Play install links on app pages and help articles
    get the site's install referrer (IA spec 9.2, WP-A 12), so every Play button has the same UTM format whoever
    wrote the page. Idempotent; dates hash this text, so the rewrite never moves a page's modified date twice."""
    s = read(relpath)
    parts = bare_of(relpath)[:-len("index.html")].strip("/").split("/") if relpath.endswith("index.html") else []
    if parts and parts[0] == "apps" and len(parts) in (2, 3):
        medium = "app_page" if len(parts) == 2 else "howto"
        lang = lang_of(relpath)
        def fix(m):
            a = BY_PACKAGE.get(m.group(1))
            return f'href="{esc(play_link(a, lang, medium))}"' if a and a.get("play") else m.group(0)
        s = PLAY_HREF_RE.sub(fix, s)
    return s

def policy_extra(a, lang, parts):
    """Inner HTML of <!-- build:extra --> on a policy page (IA spec 3.2(7)): the app page, one help article, and for
    AXFamily the related documents (policy, account deletion, terms). Anchors carry the app or document name.
    parts: the path below /privacy/, e.g. ["blocks"] or ["axfamily", "terms"]."""
    t = T[lang]
    lis = []
    if a and len(parts) == 1 and a.get("app_path"):
        lis.append(f'<li>{t["pol_app"]}: <a href="{app_url(a, lang)}">{esc(a[lang]["name"])}</a></li>')
        arts = dict(article_links(lang, a["app_path"]))
        first = None
        for _, slug in a[lang].get("tasks") or []:  # the article the app page lists first, else the newest
            u = url(lang, f"/apps/{a['app_path']}/{slug}/") if slug else None
            if u in arts: first = u; break
        if not first and arts: first = next(iter(arts))
        if first: lis.append(f'<li>{t["pol_guide"]}: <a href="{first}">{esc(arts[first])}</a></li>')
    if parts and parts[0] == "axfamily" and a:
        docs = [(url(lang, "/privacy/axfamily/"), t["policy_of"].format(name=a[lang]["name"]))]
        docs += [(url(lang, f"/privacy/axfamily/{slug}/"), label) for slug, label in t["axfamily_docs"]]
        here = url(lang, "/privacy/" + "/".join(parts) + "/")
        lis += [f'<li><a href="{u}">{esc(n)}</a></li>' for u, n in docs if u != here and exists(relpath_of(u))]
    if not lis: return ""
    return (f'\n    <section aria-labelledby="pol-related">\n      <h2 id="pol-related">{t["pol_related_h"]}</h2>\n'
            '      <ul class="related-links">' + "".join(f"\n        {x}" for x in lis) + "\n      </ul>\n    </section>\n    ")

def wrap_hand(relpath):
    s = hand_source(relpath)
    lang = lang_of(relpath)
    t = T[lang]
    mt = re.search(r"<title>(.*?)</title>", s, re.S)
    mm = re.search(r"<main[^>]*>\n?(.*?)\n?\s*</main>(?!.*</main>)", s, re.S)  # the last </main> closes it
    desc = None
    for tag in re.findall(r"<meta\b[^>]*>", s):
        if re.search(r'name="description"', tag):
            c = re.search(r'content="([^"]*)"', tag)
            desc = html.unescape(c.group(1)) if c else None
    if not (mt and mm and desc):
        raise SystemExit(f"{relpath}: a hand-written page needs <title>, <meta name=\"description\"> and <main> (missing: "
                         + ", ".join(n for n, v in (("title", mt), ("description", desc), ("main", mm)) if not v) + ")")
    title = html.unescape(mt.group(1).strip())
    main = mm.group(1)
    main = re.sub(r'^\s*<nav class="crumbs".*?</nav>\n?', "", main, flags=re.S)  # ours, re-added below
    path = "/" + relpath[:-len("index.html")]
    bare = "/" + bare_of(relpath)[:-len("index.html")]
    other_path = url(other(lang), bare)
    alt = other_path if exists(relpath_of(other_path)) else None
    parts = bare.strip("/").split("/")
    noindex = relpath in NOINDEX_PATHS
    a, items, lds, current, og, og_type, app_scope = None, [], [], None, None, "website", None
    main_cls = ""
    isolated = False
    headline = h1_text(main) or title
    page_dm = dates.iso_datetime(modified(relpath)) if not noindex else None
    if parts[0] == "apps" and len(parts) == 2:
        a = BY_APP_PATH.get(parts[1]); current = "apps"; app_scope = a
        items = [(t["apps"], url(lang, "/apps/")), (a[lang]["name"] if a else headline, None)]
        if a:
            ld = app_ld(a, lang, path, title)
            # featureList (IA 5.2) from the hand page's own feature headings: the h3s of <section> h2#features
            fs = re.search(r'<h2 id="features"[^>]*>.*?</h2>(.*?)(?=<h2\b|$)', main, re.S)
            feats = [plain(x) for x in re.findall(r"<h3[^>]*>(.*?)</h3>", fs.group(1), re.S)] if fs else []
            if feats and "featureList" not in ld["@graph"][1]: ld["@graph"][1]["featureList"] = feats
            lds.append(ld); og = app_og(a, lang)
            main = set_block(main, "tasks", tasks_block(a, lang), after_hero(main))
            main = set_block(main, "extra", app_extra(a, lang, relpath))
        if re.search(r'^\s*<section class="facts"', dates.strip_build_blocks(main), re.M):
            main_cls = "app-layout"
    elif parts[0] == "apps" and len(parts) == 3:
        a = BY_APP_PATH.get(parts[1]); current = "apps"; app_scope = a; og_type = "article"
        items = [(t["apps"], url(lang, "/apps/"))]
        if a: items.append((a[lang]["name"], app_url(a, lang)))
        items.append((headline, None))
        imgs = article_images(a, parts[2], lang) if a else []
        if not imgs and a and exists(app_og(a, lang).lstrip("/")):
            imgs = [app_og(a, lang)]  # no capture in the article (e.g. pilot/pricing): Article still needs an image
        og = imgs[0] if imgs else None
        lds.append({"@context": "https://schema.org", "@type": "Article", "@id": SITE + path + "#article",
                    "headline": headline, "description": desc, "url": SITE + path, "mainEntityOfPage": SITE + path, "inLanguage": lang,
                    "datePublished": dates.iso_datetime(published(relpath)), "dateModified": page_dm,
                    **({"image": [SITE + x for x in imgs]} if imgs else {}),
                    "author": ORG_REF, "publisher": ORG_REF, "isPartOf": SITE_REF,
                    **({"about": {"@id": SITE + app_url(a, lang) + "#app"}} if a else {})})
        main = set_block(main, "meta", meta_line(lang, relpath, main), after_lead(main))
        main = set_block(main, "toc", toc_inner(main, lang), after_hero(main))
        main = set_block(main, "extra", "") if BLOCK_RE("extra").search(main) else main
    elif parts[0] == "privacy" and len(parts) in (2, 3):
        a = BY_PRIVACY_PATH.get(parts[1]); current = "privacy"; og_type = "article"; og = f"/assets/og/privacy-{lang}.png"
        name = a[lang]["name"] if a else headline
        items = [(t["privacy"], url(lang, "/privacy/"))]
        if len(parts) == 3:
            items += [(name, url(lang, f"/privacy/{parts[1]}/")), (headline, None)]
        else:
            items.append((name, None))
        lds.append({"@context": "https://schema.org", "@type": "WebPage", "@id": SITE + path, "name": title, "url": SITE + path,
                    "inLanguage": lang, "isPartOf": SITE_REF, "publisher": ORG_REF, "dateModified": page_dm,
                    **({"about": {"@id": SITE + app_url(a, lang) + "#app"}} if a and a.get("app_path") and len(parts) == 2 else {})})
        isolated = legal_chrome.is_isolated(a, parts)
        # isolated: no related links either (the app page leads to pricing); an empty block keeps <main> stable
        main = set_block(main, "extra", "" if isolated else policy_extra(a, lang, parts[1:]))
        # side TOC like /about/, unless the policy carries its own contents list (cardrawer, axfamily)
        own = re.search(r'<nav\b(?:(?!</nav>).)*?href="#', dates.strip_build_blocks(main), re.S)
        toc = "" if own else toc_inner(main, lang)
        # a body link with the same text as a TOC entry (axfamily "9-4. Ads" -> #ads) keeps its anchor: one text, one URL
        for href, text in re.findall(r'<a href="(#[^"]+)">(.*?)</a>', dates.strip_build_blocks(main)):
            toc = re.sub(r'href="#[^"]+">' + re.escape(text) + '</a>', lambda _: f'href="{href}">{text}</a>', toc)
        main = set_block(main, "toc", toc, after_hero(main))
    elif parts[0] == "ax" and len(parts) == 1:
        current = "ax"; og = f"/assets/og/ax-{lang}.png"
        items = [(t["ax"], None)]
        # the hub is board page 1: series cards, the newest AX_BOARD_PAGE notes as a 2-line board, topic chips, search,
        # all rebuilt from ax/<slug>/ + data/ax.json on every build (2026-11-13 redesign; the hand file holds only text)
        board, rows = ax_board(1, lang)
        main = set_block(main, "ax-list", board)
        if BLOCK_RE("ax-series").search(main):
            main = set_block(main, "ax-series", ax_series_cards(lang))
        if BLOCK_RE("ax-search").search(main):
            main = set_block(main, "ax-search", ax_extras.search_block(lang, url(lang, "/ax/search.json")))
        if BLOCK_RE("ax-topics").search(main):
            main = set_block(main, "ax-topics", ax_topic_chips(lang))
        if BLOCK_RE("ax-count").search(main):
            main = set_block(main, "ax-count", esc(AX_T[lang]["ax_board_n"].format(n=len(ax_articles(lang)))))
        lds.append({"@context": "https://schema.org", "@type": "CollectionPage", "@id": SITE + path, "name": title, "description": desc,
                    "url": SITE + path, "inLanguage": lang, "isPartOf": SITE_REF, "publisher": ORG_REF, "dateModified": page_dm,
                    "mainEntity": {"@type": "ItemList", "@id": SITE + path + "#list", "itemListElement": [
                        {"@type": "ListItem", "position": i + 1, "url": SITE + u} for i, (u, _, _) in enumerate(rows)]}})
        main = set_block(main, "extra", "\n    " + updated_p(lang, relpath) + "\n    ")
        main_cls = "ax-hub"
    elif parts[0] == "ax" and len(parts) == 2:
        current = "ax"; og_type = "article"
        og = f"/assets/og/ax-{parts[1]}-{lang}.png"
        tp = ax_topic_of(path)
        items = [(t["ax"], url(lang, "/ax/"))] + ([(tp[lang]["name"], ax_topic_url(tp, lang))] if tp else []) + [(headline, None)]
        lds.append({"@context": "https://schema.org", "@type": "Article", "@id": SITE + path + "#article",
                    "headline": headline, "description": desc,
                    "url": SITE + path, "mainEntityOfPage": SITE + path, "inLanguage": lang,
                    "articleSection": tp[lang]["name"] if tp else t["ax"],
                    "datePublished": dates.iso_datetime(published(relpath)), "dateModified": page_dm,
                    **({"image": imgs} if (imgs := [SITE + x for x in dict.fromkeys(
                        [x for x in (og, f"/assets/ax/cover/{parts[1]}-{lang}.webp") if exists(x.lstrip("/"))]
                        + ax_extras.figures(main))]) else {}),
                    "author": ORG_REF, "publisher": ORG_REF, "isPartOf": SITE_REF})
        main = set_block(main, "meta", meta_line(lang, relpath, main, tp[lang]["name"] if tp else t["ax"]), after_lead(main))
        # series: a line under the meta and the contents box at the end, unless the body already has ax_md's own (windows-harness)
        own_series = re.search(r'<nav class="box" aria-label="(?:연재 목차|Series contents)"', dates.strip_build_blocks(main))
        if not own_series and ax_series_pos(parts[1], lang):
            main = set_block(main, "series", ax_series_top(parts[1], lang), BLOCK_RE("meta").search(main).end())
            faq0 = re.search(r'\n\s*<section aria-labelledby="faq">', main)
            main = set_block(main, "series-nav", ax_series_nav(parts[1], lang), faq0.start() if faq0 else None)
        # inquiry boxes: one before the middle body h2, one before the FAQ (ax_extras)
        mid = ax_extras.middle_h2(main)
        main = set_block(main, "cta-mid", ax_extras.cta_mid(lang, EMAIL, headline), mid)
        faq = re.search(r'\n\s*<section aria-labelledby="faq">', main)
        main = set_block(main, "cta", ax_extras.cta_end(lang, EMAIL, headline), faq.start() if faq else None)
        # cover: the note's figures on the topic colour, first thing in the hero (tools/ax_cover.py); site.css turns
        # the hero's eyebrow, h1, lead and meta into a band of that colour beside (desktop) or under (phone) the art
        cover = f"/assets/ax/cover/{parts[1]}-{lang}.webp"
        hero = re.search(r'<section class="hero"[^>]*>', main)
        if hero and exists(cover.lstrip("/")):
            main = set_block(main, "cover", f'<figure class="ax-cover-art"><img src="{cover}" width="1200" height="900" alt=""'
                                            f' fetchpriority="high" decoding="async"></figure>', hero.end())
            main_cls = f"ax-note ax-t-{tp['id'] if tp else 'workflow'}"
        # ads: one unit after the intro, one before the closing inquiry box, a left rail and one under the side TOC
        main = set_block(main, "ad-1", ax_extras.ad_unit(ADS, "in_article", lang), after_hero(main))
        cta_end = BLOCK_RE("cta").search(main)
        main = set_block(main, "ad-2", ax_extras.ad_unit(ADS, "in_article", lang), cta_end.start() if cta_end else None)
        toc = toc_inner(main, lang)
        if toc:
            inline, nav = toc.split("</details>", 1)
            toc = f'{inline}</details><div class="ax-side">{nav}{ax_extras.ad_unit(ADS, "rail_right", lang)}</div>'
        main = set_block(main, "toc", toc, after_hero(main))
        main = set_block(main, "ad-rail", ax_extras.ad_unit(ADS, "rail_left", lang), BLOCK_RE("toc").search(main).end())
        # related: newest notes of the same topic first, then the newest of other topics, AX_RELATED in all
        allx = [(u, n) for u, n, _ in ax_articles(lang) if u != path]
        # a series note already links its neighbours and the series page: half the related list (40 KB budget)
        my_sr = ax_series_pos(parts[1], lang)
        n_rel = 2 if my_sr else AX_RELATED
        if my_sr:  # same-series notes are in the series box already
            allx = [x for x in allx if (AX_SERIES_OF.get(ax_slug(x[0])) or (None,))[0] is not my_sr[0]]
        same = [x for x in allx if tp and ax_topic_of(x[0]) is tp][:n_rel - 2]
        others = same + [x for x in allx if x not in same][:n_rel - len(same)]
        extra = ""
        if others:
            lis = "".join(f'\n        <li><a href="{u}">{esc(n)}</a></li>' for u, n in others)
            more = (f'<a href="{ax_topic_url(tp, lang)}">{esc(AX_T[lang]["ax_topic_all"].format(name=tp[lang]["name"]))}</a> · ' if tp and same else "")
            extra = (f'\n    <section aria-labelledby="ax-related-heading">\n      <h2 id="ax-related-heading">{t["ax_related_h"]}</h2>\n      <ul>{lis}\n      </ul>\n'
                     f'      <p>{more}<a href="{url(lang, "/ax/")}">{t["ax_more"]}</a></p>\n    </section>\n    ')
        main = set_block(main, "extra", extra)
    elif parts[0] == "about" and len(parts) == 1:
        current = "about"; og = f"/assets/og/about-{lang}.png"
        items = [(t["about"], None)]
        pub = published(relpath)
        lds.append({"@context": "https://schema.org", "@type": "ProfilePage", "@id": SITE + path, "url": SITE + path, "name": title,
                    "inLanguage": lang, "isPartOf": SITE_REF, "dateCreated": dates.iso_datetime(pub), "dateModified": page_dm,
                    "mainEntity": org_full(lang)})
        main = set_block(main, "toc", toc_inner(main, lang), after_hero(main))
    elif parts[0] == "design" and len(parts) == 1:
        main = set_block(main, "toc", toc_inner(main, lang), after_hero(main))
    if current not in ("privacy", None) or (parts[0] == "apps"):
        qa = [(plain(q), plain(x)) for q, x in re.findall(r"<details>\s*<summary>(.*?)</summary>(.*?)</details>", dates.strip_build_blocks(main), re.S)]
        if qa: lds.append(faq_ld(qa))
    if noindex:
        lds, nav = [], ""
    else:
        nav, bc = crumbs(lang, items)
        lds.append(bc)
        nav = f"    {nav}\n"
    h = head(lang, title, desc, path, alt, og_type=og_type, og_image=og, lds=lds)
    other_href = alt or url(other(lang), "/")
    if isolated:  # legal page an app opens: no breadcrumbs, no site header/footer (they lead to home, hub, pricing)
        base = privacy_url(a, lang)
        return page(lang, h, ' class="page-read"', legal_chrome.header(t, a, lang, base, other_href, BRAND_MARK), main,
                    legal_chrome.footer(t, a, lang, base, EMAIL, here_href=path), app=app_scope)
    if main_cls == "ax-hub":
        h = ax_css(h); main_cls = ""
    if main_cls.startswith("ax-note"):
        h = h.replace("</head>", f'  <link rel="stylesheet" href="/assets/ax.css?v={CSSV}">\n'
                                 + (f"  {ax_extras.ads_head(ADS)}\n" if ADS["on"] else "") + "</head>")
    # body class (site.css "layout"): hubs use the full width like home; app pages grid main themselves (app-layout);
    # everything else is a reading page (text column, side TOC when there is one)
    body = ' class="page-hub"' if parts == ["ax"] else "" if main_cls == "app-layout" else ' class="page-read"'
    return page(lang, h, body, header(lang, current, other_href), nav + main, footer(lang), app=app_scope,
                main_cls=main_cls)

def build_404():
    """noindex only: no canonical, og:url, hreflang, breadcrumbs or JSON-LD (IA spec 3.2(8)). Links: /, /apps/, /ax/, /privacy/, /en/."""
    t = T["ko"]; te = T["en"]
    main = f'''    <section class="notfound hero">
      <h1>{t["nf_h"]}</h1>
      <p class="lead">{t["nf_p"]}</p>
      <div class="actions"><a class="button" href="/">{t["nf_home"]}</a><a class="button button--outline" href="/apps/">{t["all_apps"]}</a></div>
      <ul class="related-links">
        <li><a href="/ax/">{t["ax_nav"]}</a></li>
        <li><a href="/privacy/">{t["privacy"]}</a></li>
      </ul>
      <p lang="en" class="muted">{te["nf_h"]}. {te["nf_p"]} <a href="/en/">{te["nf_home"]}</a></p>
    </section>'''
    h = head("ko", t["nf_title"], t["nf_p"], "/404.html", None)
    return page("ko", h, "", header("ko", None, "/en/"), main, footer("ko"))

# ---------------------------------------------------------------- HTML site map (people and crawlers; the XML files are for search consoles)
SITEMAP_T = {
    "ko": {"title": "사이트맵", "lead": "SugarMount의 모든 페이지를 한곳에 모았습니다. 앱 소개와 도움말, AX 노트, 개인정보처리방침을 묶음별로 찾을 수 있습니다.",
           "main_h": "주요 페이지", "apps_h": "앱과 도움말", "ax_h": "AX 노트 전체", "privacy_h": "개인정보처리방침", "n": "{n}쪽"},
    "en": {"title": "Site map", "lead": "Every page on SugarMount in one place: app pages and help articles, AX notes by topic, and the privacy policies.",
           "main_h": "Main pages", "apps_h": "Apps and help", "ax_h": "All AX notes", "privacy_h": "Privacy policies", "n": "{n} pages"},
}

def sitemap_page_input(lang, pages):
    """Hash input for /sitemap/: the list of pages it links to (titles live on those pages, not here)."""
    return dates.data_input("sitemap", sorted(p for p in pages if lang_of(p) == lang and p not in NOINDEX_PATHS and bare_of(p) != "sitemap/index.html"))

def build_sitemap_page(lang, outputs, pages):
    """Every indexable page of one language as plain links: main pages, apps with their help articles, AX notes by topic
    (with dates), privacy policies, then anything else. Linked from every footer, so no page is more than two clicks deep."""
    t, st = T[lang], SITEMAP_T[lang]
    path = url(lang, "/sitemap/")
    def title_of(rp):
        return h1_text(outputs.get(rp) or read(rp)) or rp
    mine = sorted(p for p in pages if lang_of(p) == lang and p not in NOINDEX_PATHS and p.endswith("index.html") and bare_of(p) != "sitemap/index.html")
    done = set()
    def li(u, label, extra=""):
        done.add(relpath_of(u))
        return f'<li><a href="{u}">{esc(label)}</a>{extra}</li>'
    main_li = "".join(li(url(lang, p), n) for p, n in (("/", "SugarMount"), ("/apps/", t["footer_all_apps"]), ("/ax/", t["ax_nav"]),
                                                      ("/about/", t["about"]), ("/privacy/", t["privacy"])) if relpath_of(url(lang, p)) in pages)
    app_rows = []
    for g, apps in grouped(lang, [a for a in APPS if app_url(a, lang) and relpath_of(app_url(a, lang)) in pages]):
        items = []
        for a in apps:
            arts = article_links(lang, a["app_path"]) if a.get("app_path") else []
            sub = "<ul>" + "".join(li(u, n) for u, n in arts) + "</ul>" if arts else ""
            items.append(li(app_url(a, lang), full_name(a, lang), sub))
        app_rows.append(f'      <h3>{esc(g)}</h3>\n      <ul>{"".join(items)}</ul>')
    ax_rows = []
    for tp, arts in ax_by_topic(lang):
        tu = ax_topic_url(tp, lang)
        head_link = f'<a href="{tu}">{esc(tp[lang]["name"])}</a>' if relpath_of(tu) in pages else esc(tp[lang]["name"])
        done.add(relpath_of(tu))
        notes = "".join(li(u, n, f' <span class="muted">{fmt_date(lang, published(relpath_of(u)))}</span>') for u, n, _ in arts)
        ax_rows.append(f'      <h3>{head_link} <span class="muted">{st["n"].format(n=len(arts))}</span></h3>\n      <ul>{notes}</ul>')
    pol = [p for p in mine if bare_of(p).startswith("privacy/") and p not in done]
    pol_li = "".join(li("/" + p[:-len("index.html")], title_of(p)) for p in sorted(pol, key=title_of))
    rest = [p for p in mine if p not in done]
    rest_li = "".join(li("/" + p[:-len("index.html")], title_of(p)) for p in rest)
    nav, bc = crumbs(lang, [(st["title"], None)])
    main = f'''    {nav}
    <header class="hero">
      <h1>{st["title"]}</h1>
      <p class="lead">{st["lead"]}</p>
    </header>

    <section aria-labelledby="sm-main">
      <h2 id="sm-main">{st["main_h"]}</h2>
      <ul>{main_li}{rest_li}</ul>
    </section>

    <section aria-labelledby="sm-apps">
      <h2 id="sm-apps">{st["apps_h"]}</h2>
{chr(10).join(app_rows)}
    </section>

    <section aria-labelledby="sm-ax">
      <h2 id="sm-ax">{st["ax_h"]}</h2>
{chr(10).join(ax_rows)}
    </section>

    <section aria-labelledby="sm-privacy">
      <h2 id="sm-privacy">{st["privacy_h"]}</h2>
      <ul>{pol_li}</ul>
    </section>'''
    title = fit_title(st["title"], lang)
    lds = [{"@context": "https://schema.org", "@type": "CollectionPage", "@id": SITE + path, "url": SITE + path, "name": title,
            "description": st["lead"], "inLanguage": lang, "isPartOf": SITE_REF, "publisher": ORG_REF,
            "dateModified": dates.iso_datetime(modified(relpath_of(path)))}, bc]
    h = head(lang, title, st["lead"], path, url(other(lang), "/sitemap/"), lds=lds)
    return page(lang, h, ' class="page-hub"', header(lang, None, url(other(lang), "/sitemap/")), main, footer(lang))

# ---------------------------------------------------------------- sitemap, feeds, robots, llms.txt
MAIN_RE = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)

def main_html(content):
    m = MAIN_RE.search(content)
    return m.group(1) if m else ""

def section_rank(relpath):
    bare = bare_of(relpath)
    return 0 if bare == "index.html" else 1 if bare.startswith("apps/") else 2 if bare.startswith("ax/") else 3

SITEMAP_PARTS = (("sitemap-main.xml", (0, 3)), ("sitemap-apps.xml", (1,)), ("sitemap-ax.xml", (2,)))  # home+about+policies, apps, AX notes

def sitemap_rank(relpath):
    """(priority, changefreq) per page kind. Hubs first, then content, policies last."""
    parts = bare_of(relpath)[:-len("index.html")].strip("/").split("/")
    if parts == [""]: return "1.0", "daily"
    if parts in (["apps"], ["ax"]): return "0.9", "daily"
    if parts[0] == "ax": return ("0.6", "weekly") if parts[1] in AX_RESERVED else ("0.8", "monthly")
    if parts[0] == "apps": return ("0.8", "weekly") if len(parts) == 2 else ("0.7", "monthly")
    if parts[0] == "privacy": return "0.3", "yearly"
    return "0.5", "monthly"

def build_sitemap(pages, outputs):
    """Plain sitemaps.org files, like any large site's: sitemap.xml is a <sitemapindex> (the file robots.txt and Search
    Console point at) over one <urlset> per section with loc, lastmod, priority and changefreq only. hreflang pairs and
    images live in each page's <head> and JSON-LD, not here."""
    files, index = {}, []
    ordered = sorted(pages, key=lambda p: (p.startswith("en/"), section_rank(p), p.count("/"), p))
    for name, ranks in SITEMAP_PARTS:
        out = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        mods = []
        for relpath in ordered:
            if not relpath.endswith("index.html") or relpath in NOINDEX_PATHS or section_rank(relpath) not in ranks: continue
            mods.append(modified(relpath))
            pri, freq = sitemap_rank(relpath)
            out += ["  <url>", f"    <loc>{SITE}/{relpath[:-len('index.html')]}</loc>", f"    <lastmod>{mods[-1]}</lastmod>",
                    f"    <priority>{pri}</priority>", f"    <changefreq>{freq}</changefreq>", "  </url>"]
        if not mods: continue
        out.append("</urlset>")
        files[name] = "\n".join(out) + "\n"
        index += ["  <sitemap>", f"    <loc>{SITE}/{name}</loc>", f"    <lastmod>{max(mods)}</lastmod>", "  </sitemap>"]
    files["sitemap.xml"] = "\n".join(['<?xml version="1.0" encoding="UTF-8"?>',
                                      '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
                                     + index + ["</sitemapindex>"]) + "\n"
    return files

def feed_kind(relpath):
    """RSS item scope (IA spec 4.3): help articles, AX notes and hub, app pages, /apps/, /about/. Not policies."""
    parts = bare_of(relpath)[:-len("index.html")].strip("/").split("/") if relpath.endswith("index.html") else [""]
    if parts[0] == "apps" and len(parts) in (1, 2, 3): return True
    if parts[0] == "ax" and len(parts) in (1, 2) and parts[-1] != "topic": return True
    return parts == ["about"]

def feed_body(content, page_url):
    """Full <main> HTML for an RSS item (IA spec 4.3): no breadcrumbs, build:meta/build:toc blocks or scripts, no build
    markers; every href/src/srcset absolute, "#x" made "{page URL}#x"; "]]>" split so the CDATA section stays whole."""
    body = main_html(content)
    body = re.sub(r'<nav class="crumbs".*?</nav>', "", body, flags=re.S)
    for name in ("meta", "toc", "ad-1", "ad-2", "ad-rail"):  # ads stay on the site, never in feeds
        body = BLOCK_RE(name).sub("", body)
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S)
    body = re.sub(r"<!-- /?build:[\w-]+ -->", "", body)
    def absol(u):
        u = u.strip()
        if u.startswith("#"): return page_url + u
        if u.startswith("/") and not u.startswith("//"): return SITE + u
        return u
    body = re.sub(r'\b(href|src)="([^"]*)"', lambda m: f'{m.group(1)}="{absol(m.group(2))}"', body)
    body = re.sub(r'\bsrcset="([^"]*)"', lambda m: 'srcset="' + ", ".join(
        " ".join([absol(p.split()[0])] + p.split()[1:]) for p in m.group(1).split(",") if p.strip()) + '"', body)
    body = re.sub(r"\n\s*\n", "\n", body).strip()
    return body.replace("]]>", "]]]]><![CDATA[>")

def build_rss(outputs, lang):
    from email.utils import format_datetime
    import datetime
    items = []
    for relpath, content in outputs.items():
        if lang_of(relpath) != lang or relpath in NOINDEX_PATHS or not feed_kind(relpath): continue
        mt = re.search(r"<title>(.*?)</title>", content, re.S)
        if not mt: continue
        pub, mod = page_dates(relpath)
        items.append((pub, mod, relpath, html.unescape(mt.group(1).strip()), content))
    items.sort(key=lambda x: x[2]); items.sort(key=lambda x: x[0], reverse=True)
    items = items[:RSS_MAX]
    def rfc(day): return format_datetime(datetime.datetime.fromisoformat(day + "T09:00:00+09:00"))
    t = T[lang]
    self_url = f"{SITE}{prefix(lang)}/rss.xml"
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">', "<channel>",
           f"  <title>{esc(t['home_title'])}</title>", f"  <link>{SITE}{url(lang, '/')}</link>",
           f"  <description>{esc(t['home_lead'])}</description>", f"  <language>{lang}</language>",
           f'  <atom:link href="{self_url}" rel="self" type="application/rss+xml"/>']
    if items: out.append(f"  <lastBuildDate>{rfc(max(x[1] for x in items))}</lastBuildDate>")
    for pub, _, relpath, title, content in items:
        link = SITE + "/" + relpath[:-len("index.html")]
        out += ["  <item>", f"    <title>{esc(title)}</title>", f"    <link>{link}</link>", f'    <guid isPermaLink="true">{link}</guid>',
                f"    <description><![CDATA[{feed_body(content, link)}]]></description>", f"    <pubDate>{rfc(pub)}</pubDate>", "  </item>"]
    out += ["</channel>", "</rss>"]
    return "\n".join(out) + "\n"

def build_robots():
    """Crawl everything public; keep build sources and repo notes out of search. Assets stay open for image search.
    One `User-agent: *` group only (a bot-specific group would drop the Disallow lines for that bot) and one Sitemap
    line: the RSS feeds are for Naver submission and subscribers, not a sitemap (IA spec 4.4)."""
    return "\n".join([
        "# SugarMount (sugarmount21.com). Generated by tools/build.py.",
        "User-agent: *",
        "Allow: /",
        "Disallow: /tools/",
        "Disallow: /data/",
        "Disallow: /AGENTS.md",
        "Disallow: /404.html",
        "",
        f"Sitemap: {SITE}/sitemap.xml",
        ""])

def build_manifest():
    """/site.webmanifest: name and icons for Android home-screen shortcuts and browsers (icons drawn by tools/og.py).
    display "browser": this is a website, not an installable app (the apps live on Google Play)."""
    return json.dumps({
        "name": "SugarMount", "short_name": "SugarMount", "lang": "ko", "start_url": "/", "scope": "/",
        "display": "browser", "background_color": "#F7FAFE", "theme_color": "#F7FAFE",
        "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/logo.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "/assets/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
                  {"src": "/assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}]},
        ensure_ascii=False, indent=2) + "\n"

def indexnow_key():
    """The public IndexNow key (data/indexnow-key.txt, tools/indexnow.py); the build serves it as /<key>.txt."""
    try:
        key = read("data/indexnow-key.txt").strip()
    except FileNotFoundError:
        return None
    if not re.fullmatch(r"[0-9a-fA-F-]{8,128}", key):
        raise SystemExit("data/indexnow-key.txt: want 8-128 characters of a-f, 0-9 or '-'")
    return key

def lead_of(relpath):
    """The <p class="lead"> right after the H1 of a hand page (used for the llms.txt summary)."""
    try:
        s = read(relpath)
    except FileNotFoundError:
        return None
    m = re.search(r'</h1>\s*<p class="lead"[^>]*>(.*?)</p>', s, re.S)
    return plain(m.group(1)) if m else None

def build_llms(outputs):
    """llms.txt (IA spec 4.6): summary = the /about/ lead (scope-limited), entry links first, one line per app,
    help articles in English and Korean, AX notes. NOINDEX pages are left out."""
    ko, en = T["ko"], T["en"]
    # summary = the /about/ section ① fixed sentence (= Organization.description), then the rest of the /about/ lead
    # (the app-count sentence), so llms.txt and the Organization node describe the entity the same way (IA 3.2(6), 4.6)
    lead = lead_of("en/about/index.html") or ""
    rest = re.sub(r"^(\w+) of them\b", r"\1 SugarMount apps", lead.split(". ", 1)[1] if ". " in lead else "")
    summary = (en["org_desc"] + " " + rest).strip()
    lines = ["# SugarMount", "", "> " + summary, "",
             f"Contact: {EMAIL}. Korean pages live at {SITE}/, English pages at {SITE}/en/.", "",
             f"- [All apps]({SITE}/en/apps/) · [앱 전체 (Korean)]({SITE}/apps/)",
             f"- [About SugarMount]({SITE}/en/about/) · [소개 (Korean)]({SITE}/about/)",
             f"- [RSS feed (English)]({SITE}/en/rss.xml) · [RSS 피드 (Korean)]({SITE}/rss.xml)",
             f"- [Site map: every page]({SITE}/en/sitemap/) · [사이트맵 (Korean)]({SITE}/sitemap/) · [XML sitemap]({SITE}/sitemap.xml)", "",
             "## Apps", ""]
    for a in APPS:
        d, k = a["en"], a["ko"]
        st = {"live": "on Google Play", "soon": "coming soon", "review": "in Play review"}[a["status"]]
        link = SITE + (app_url(a, "en") or privacy_url(a, "en"))
        name = d["name"] if d["name"] == k["name"] else f"{d['name']} / {k['name']}"
        lines.append(f"- [{name}]({link}): {d['tagline']} Package {a['package']}, {st}.")
    # no "Privacy policies" section: policies are noindex (tools/noindex.py)
    lines += ["", "## Facts", ""]
    for q, x in en["home_faq"]:
        lines.append(f"- {q} {x}")
    for lang, h in (("en", "## Help articles (English)"), ("ko", "## Help articles (Korean)")):
        arts = []
        for relp in sorted(outputs):
            parts = bare_of(relp)[:-len("index.html")].strip("/").split("/") if relp.endswith("index.html") else []
            if lang_of(relp) != lang or len(parts) != 3 or parts[0] != "apps" or relp in NOINDEX_PATHS: continue
            c = outputs[relp]
            md = re.search(r'<meta name="description" content="([^"]*)"', c)
            h1 = h1_text(main_html(c))
            if h1 and md: arts.append(f"- [{h1}]({SITE}/{relp[:-len('index.html')]}): {html.unescape(md.group(1))}")
        if arts: lines += ["", h, ""] + arts
    groups = ax_by_topic("en")
    if groups:
        lines += ["", "## AX notes", "", f"How SugarMount apps are built and shipped with an AI coding agent, with measured numbers. Index: {SITE}/en/ax/ · Korean: {SITE}/ax/"]
        for tp, arts in groups:
            arts = [x for x in arts if x[0].lstrip("/") + "index.html" not in NOINDEX_PATHS]  # topic pages, folded notes
            if arts: lines += ["", f"### {tp['en']['name']}", ""] + [f"- [{n}]({SITE}{u}): {d}" for u, n, d in arts]
    lines += ["", "## Optional", "", f"- [Korean home (한국어)]({SITE}/): {ko['home_lead']}", f"- [Google Play developer page]({PLAY_DEV})", ""]
    return "\n".join(lines)

# ---------------------------------------------------------------- generated CSS (SDS 4.1, 5.2; IA 9.1)
FONT_SKIP_TAGS = {"head", "script", "style", "template", "noscript", "code", "pre", "kbd", "samp", "svg", "textarea"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
CSS_CHARS = "•…0123456789."  # characters site.css draws itself in Pretendard (list markers, line-clamp, counters); the
                               # breadcrumb "›" is drawn in --sds-font-system so it does not pull a 25 KB subset

class _FontChars(HTMLParser):
    """Characters a page renders in the Pretendard stack. Left out (SDS 5.2-4): code/pre (mono stack), .sym, and on
    English pages any [lang=ko] subtree (site.css draws those in the system font)."""
    def __init__(self, lang):
        super().__init__(convert_charrefs=True)
        self.lang, self.stack, self.chars = lang, [], set()
    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS: return
        a = dict(attrs)
        skip = (tag in FONT_SKIP_TAGS or "sym" in (a.get("class") or "").split()
                or (self.lang == "en" and (a.get("lang") or "").split("-")[0] == "ko"))
        self.stack.append((tag, skip or (self.stack[-1][1] if self.stack else False)))
    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]; return
    def handle_data(self, data):
        if not (self.stack and self.stack[-1][1]):
            self.chars.update(data)

def font_chars(outputs):
    chars = set(CSS_CHARS)
    for relpath, content in outputs.items():
        if relpath.endswith(".html"):
            p = _FontChars(lang_of(relpath)); p.feed(content); p.close()
            chars |= p.chars
    return "".join(sorted(c for c in chars if not c.isspace()))

def generated_css(outputs):
    """{relpath: text} of assets/sds-apps.css and assets/fonts/pretendard.css, made in memory from the rendered pages."""
    return {"assets/sds-apps.css": sds_apps.sds_apps_css(APPS),
            "assets/fonts/pretendard.css": sds_apps.pretendard_css(font_chars(outputs))}

# ---------------------------------------------------------------- --check gates beyond tools/checks.py
def sds_gates(css_out):
    """SDS 4.3 (contrast per app, generated tokens = computed tokens) and 6.0.3 (header mark colours = og.py)."""
    errs = []
    for r in sds_apps.audit(APPS):
        if r["fail"]: errs.append(f"SDS contrast {r['id']}: {', '.join(r['fail'])}")
    css = css_out["assets/sds-apps.css"]
    for a in sds_apps._apps(APPS):
        want = sds_apps.accent_tokens(a["accent"])
        for mode in ("light", "dark"):
            if sds_apps.resolved_tokens(css, a["id"], mode == "dark") != want[mode]:
                errs.append(f"SDS T1 {a['id']} {mode}: assets/sds-apps.css tokens differ from accent_tokens()")
    og = read("tools/og.py")
    mo = re.search(r'MARK_TOP, MARK_LEFT, MARK_RIGHT, MARK_EDGE = "(#\w+)", "(#\w+)", "(#\w+)", "(#\w+)"', og)
    ms = re.search(r"--sds-mark-top:(#\w+);--sds-mark-left:(#\w+);--sds-mark-right:(#\w+);--sds-mark-edge:(#\w+);", read("assets/site.css"))
    if not (mo and ms) or [x.upper() for x in mo.groups()] != [x.upper() for x in ms.groups()]:
        errs.append("SDS mark: site.css --sds-mark-* (light) must equal tools/og.py MARK_* (favicon, logo, header)")
    if 'class="t"' not in BRAND_MARK or 'fill="#' in BRAND_MARK:
        errs.append("SDS mark: BRAND_MARK must take its colours from classes (python tools/og.py --svg)")
    return errs

# ---------------------------------------------------------------- main
def all_pages():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("tools", "data", "assets")]
        for f in fn:
            if f == "index.html" or (dp == ROOT and f == "404.html"):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/"))
    return sorted(p for p in out if p not in legal_chrome.STANDALONE_PATHS)

def validate():
    """Fail on data that would produce broken links; warn about policy pages missing from apps.json."""
    errors, ids = [], set()
    for a in APPS:
        if a["id"] in ids: errors.append(f"duplicate id {a['id']}")
        ids.add(a["id"])
        for lang in ("ko", "en"):
            if lang not in a: errors.append(f"{a['id']}: missing {lang}"); continue
            for k in ("name", "brand", "tagline", "desc"):
                if not a[lang].get(k): errors.append(f"{a['id']}.{lang}: missing {k}")
        if not a.get("privacy_path"): errors.append(f"{a['id']}: missing privacy_path")
        for lang in ("", "en/"):
            if a.get("privacy_path") and not os.path.exists(rel(f"{lang}privacy/{a['privacy_path']}/index.html")):
                errors.append(f"{a['id']}: {lang}privacy/{a['privacy_path']}/index.html does not exist")
            if a.get("page") == "hand" and not os.path.exists(rel(f"{lang}apps/{a['app_path']}/index.html")):
                errors.append(f"{a['id']}: page is hand but {lang}apps/{a['app_path']}/index.html does not exist")
        if a.get("page") in ("hand", "generated") and not a.get("app_path"): errors.append(f"{a['id']}: page {a['page']} needs app_path")
        if a.get("page") == "none" and a.get("app_path"): errors.append(f"{a['id']}: page none but app_path set")
        for ext in (".png", ".webp"):
            if not os.path.exists(rel(a["icon"].lstrip("/") + ext)): errors.append(f"{a['id']}: missing {a['icon']}{ext}")
        if a["status"] not in ("live", "soon", "review"): errors.append(f"{a['id']}: bad status")
        if a.get("play") and a["status"] != "live": errors.append(f"{a['id']}: play is true but status is not live")
        for lang in ("ko", "en"):
            for row in a.get(lang, {}).get("tasks") or []:
                if not (isinstance(row, list) and len(row) == 2 and isinstance(row[0], str)):
                    errors.append(f"{a['id']}.{lang}.tasks: want [sentence, slug or null], got {row!r}")
            for r in a.get(lang, {}).get("releases") or []:
                if not (isinstance(r, dict) and {"version", "date", "note"} <= set(r) and dates.DAY_RE.match(r["date"])):
                    errors.append(f"{a['id']}.{lang}.releases: want {{version, date YYYY-MM-DD, note}}, got {r!r}")
    for tp in AXD["topics"]:
        if not re.fullmatch(r"[a-z0-9-]+", tp["id"]): errors.append(f"data/ax.json: bad topic id {tp['id']!r}")
        for lang in ("ko", "en"):
            if not (tp.get(lang, {}).get("name") and tp[lang].get("desc")): errors.append(f"data/ax.json: topic {tp['id']}.{lang} needs name and desc")
    for lang in ("", "en/"):
        base = rel(lang + "ax")
        for slug in (sorted(os.listdir(base)) if os.path.isdir(base) else []):
            if not os.path.isfile(os.path.join(base, slug, "index.html")): continue
            if AX_NOTE_TOPIC.get(slug) not in AX_TOPICS:
                errors.append(f"{lang}ax/{slug}/: add \"{slug}\": \"<topic id>\" to notes in data/ax.json")
    for slug in AX_NOTE_TOPIC:
        if slug in AX_RESERVED: errors.append(f"data/ax.json: the note slug '{slug}' is reserved (topic, series and board pages)")
    seen = {}
    for sr in AX_SERIES:
        for slug in sr["slugs"]:
            if slug not in AX_NOTE_TOPIC: errors.append(f"data/ax.json: series {sr['id']} names {slug}, which is not a note")
            if slug in seen: errors.append(f"data/ax.json: {slug} is in two series ({seen[slug]}, {sr['id']})")
            seen[slug] = sr["id"]
        if not os.path.isfile(rel(f"ax/{slug}/index.html")): errors.append(f"data/ax.json: note {slug} has no ax/{slug}/index.html")
    known = {a.get("privacy_path") for a in APPS} | {a.get("app_path") for a in APPS}
    for p in all_pages():
        parts = p.split("/")
        if parts[0] == "en": parts = parts[1:]
        if len(parts) == 3 and parts[0] in ("apps", "privacy") and parts[1] not in known:
            print(f"warning: {p} is not in data/apps.json (no home card, list entry or footer link)", file=sys.stderr)
    if errors:
        raise SystemExit("data/apps.json / data/ax.json problems:\n  " + "\n  ".join(errors))

def main():
    global STORE
    check = "--check" in sys.argv
    validate()
    STORE = dates.ContentDates(check=check)
    GEN_INPUTS.clear(); GEN_INPUTS.update(generated_inputs())
    outputs = {}
    generated = {"404.html"}
    for lang in ("ko", "en"):
        p = "en/" if lang == "en" else ""
        outputs[p + "index.html"] = build_home(lang)
        outputs[p + "apps/index.html"] = build_apps_hub(lang)
        outputs[p + "privacy/index.html"] = build_privacy_index(lang)
        generated |= {p + "index.html", p + "apps/index.html", p + "privacy/index.html"}
        for a in APPS:
            if a.get("page") == "generated":
                gp = f"{p}apps/{a['app_path']}/index.html"
                generated.add(gp); outputs[gp] = build_app(a, lang)
    for gp, (tp, lang) in ax_topic_pages().items():
        generated.add(gp); outputs[gp] = build_ax_topic(tp, lang)
    for gp, (sr, lang) in ax_series_pages().items():
        generated.add(gp); outputs[gp] = build_ax_series(sr, lang)
    for gp, (pn, lang) in ax_board_page_paths().items():
        generated.add(gp); outputs[gp] = build_ax_page(pn, lang)
    outputs["404.html"] = build_404()
    generated |= {"sitemap/index.html", "en/sitemap/index.html"}  # built last, below
    stale = [p for p in all_pages() if bare_of(p).startswith(("ax/topic/", "ax/series/", "ax/page/")) and p not in generated]  # topic left without notes
    for p in all_pages():
        if p not in generated and p not in stale:
            outputs[p] = wrap_hand(p)
    pages = (set(all_pages()) - set(stale)) | {p for p in outputs if p.endswith("index.html")}
    for lang in ("ko", "en"):  # the HTML site map last: it lists every other page
        sp = ("en/" if lang == "en" else "") + "sitemap/index.html"
        pages.add(sp); generated.add(sp)
        GEN_INPUTS[sp] = sitemap_page_input(lang, pages)
        outputs[sp] = build_sitemap_page(lang, outputs, pages)
    for p in sorted(pages):
        if p not in NOINDEX_PATHS: page_dates(p)  # every indexable page has an entry, even if nothing above asked
    # generated CSS first (in memory, from the rendered pages' characters), then ONE version for all three stylesheets,
    # substituted into every page before anything is written (IA spec 9.1)
    css_out = generated_css(outputs)
    version = css_version([css_out[k] for k in sorted(css_out)])
    for p in outputs:
        outputs[p] = outputs[p].replace(CSSV, version)
    outputs.update(css_out)
    for lang in ("ko", "en"):  # the hub's search index (ax_extras.search_block)
        outputs[("en/" if lang == "en" else "") + "ax/search.json"] = ax_extras.search_json(
            [(u, n, d, (ax_topic_of(u) or {}).get(lang, {}).get("name", ""), ax_type(u), fmt_date(lang, published(relpath_of(u))))
             for u, n, d in ax_articles(lang)])
    outputs["llms.txt"] = build_llms(outputs)
    outputs.update(build_sitemap(pages, outputs))
    outputs["rss.xml"] = build_rss(outputs, "ko")
    outputs["en/rss.xml"] = build_rss(outputs, "en")
    outputs["robots.txt"] = build_robots()
    outputs["site.webmanifest"] = build_manifest()
    if (adstxt := ax_extras.ads_txt(ADS)): outputs["ads.txt"] = adstxt
    key = indexnow_key()
    if key: outputs[key + ".txt"] = key
    for gone in STORE.unused():  # pages that no longer exist (or became NOINDEX) leave content-dates
        del STORE.entries[gone]
    outputs["data/content-dates.json"] = STORE.dumps()
    # site gates (tools/checks.py) over the in-memory outputs, plus the SDS gates
    report = checks.run(ROOT, outputs)
    sds_errs = sds_gates(css_out)
    changed = []
    for p, content in sorted(outputs.items()):
        full = rel(p)
        old = open(full, encoding="utf-8").read() if os.path.exists(full) else None
        if old != content:
            changed.append(p)
            if not check:
                os.makedirs(os.path.dirname(full) or ROOT, exist_ok=True)
                with open(full, "w", encoding="utf-8") as f: f.write(content)
    for p in stale:
        changed.append(p + " (stale AX topic page)")
        if not check: os.remove(rel(p))
    errors = report.errors + sds_errs
    if check:
        failed = False
        if changed:
            print("out of date:", *changed, sep="\n  "); failed = True
        if errors:
            report.print(warnings=False)
            for e in sds_errs: print("error:", e)
            failed = True
        if failed:
            print(f"--check failed: {len(changed)} file(s) out of date, {len(errors)} gate error(s)"); sys.exit(1)
        print(f"up to date; gates passed ({len(report.warnings)} warning(s))")
    else:
        print(f"{len(outputs)} files, {len(changed)} changed")
        if errors or report.warnings:
            counts = {}
            for i in report.issues: counts[(i.level, i.code)] = counts.get((i.level, i.code), 0) + 1
            print("gates:", ", ".join(f"{n} {lvl} {code}" for (lvl, code), n in sorted(counts.items())),
                  *(f"\n  {e}" for e in sds_errs), "\n  details: python tools/build.py --check")

if __name__ == "__main__":
    main()
