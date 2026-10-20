/* ============================================================
   패턴 의뢰 앱(PWA) 서비스워커
   · 하는 일: 화면 «껍데기»(intake.html·css·js·목록 파일·아이콘)만 이 폰에 보관해 둔다.
       → 앱 아이콘을 눌렀을 때 전파가 약해도 화면 틀은 뜨고 «연결 없음» 을 알려 준다.
   · 하지 않는 일: /api(그레이더 서버)·Supabase(의뢰·사진·로그인)·다른 사이트 요청은
       손대지 않는다 — 언제나 네트워크로 간다(보관하면 옛 의뢰·남의 사진이 남을 수 있다).
   · 껍데기도 «네트워크 먼저» — 연결되면 늘 새 화면을 받고, 끊겼을 때만 보관본을 쓴다.
   · 화면을 고쳐 배포할 때 VERSION 을 올리면 옛 보관함을 지운다.
   ============================================================ */
const VERSION = "intake-shell-v1";

// 보관할 껍데기 — 주소의 경로(pathname)로 맞춘다. ?v=… 꼬리는 무시한다
const SHELL = [
  "/static/screens/intake.html",
  "/static/screens/app.css",
  "/static/screens/intake.webmanifest",
  "/static/screens/intake-icons/icon-192.png",
  "/static/screens/intake-icons/icon-512.png",
  "/static/screens/intake-icons/apple-touch-icon-180.png",
  "/static/styles.css",
  "/static/tokens/fonts.css",
  "/static/tokens/colors.css",
  "/static/tokens/typography.css",
  "/static/tokens/spacing.css",
  "/static/tokens/base.css",
  "/static/intake/diagram.js",
  "/static/intake/catalog.json",
  "/static/assets/logos/stiz-favicon-32.png",
];
const SHELL_SET = new Set(SHELL);

// 연결도 없고 보관본도 없을 때 보여 줄 한 장짜리 화면
const OFFLINE_HTML = '<!doctype html><html lang="ko"><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1"><title>패턴 의뢰</title>' +
  '<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f6f8fa;color:#161a1e;font:16px/1.5 system-ui,sans-serif;text-align:center;padding:24px}' +
  'button{margin-top:16px;height:46px;padding:0 20px;border-radius:10px;border:1px solid #d0d7de;background:#fff;font:inherit;font-weight:600}</style></head>' +
  '<body><div><b>연결 없음</b><p>인터넷이 연결되면 다시 열어 주세요.</p><button onclick="location.reload()">다시 열기</button></div></body></html>';

self.addEventListener("install", (event) => {
  // 하나가 실패해도 설치는 끝낸다(없는 파일 하나 때문에 앱 설치가 막히지 않게)
  event.waitUntil(caches.open(VERSION).then((c) => Promise.all(SHELL.map((p) => c.add(p).catch(() => {})))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  // 판 번호가 다른 옛 보관함은 지운다
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith("intake-shell-") && k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                     // 저장·업로드는 손대지 않는다
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;      // Supabase·CDN·구글 — 네트워크 그대로
  if (url.pathname.startsWith("/api/")) return;         // 그레이더 서버 API — 네트워크 그대로
  const isNav = req.mode === "navigate";
  if (!SHELL_SET.has(url.pathname)) {
    // 앱 안에서 가는 로그인 화면만 «끊겼을 때 연결 없음 한 장» 을 붙인다.
    // 같은 폴더의 다른 화면(작업·패턴 등)은 아예 손대지 않는다
    if (isNav && url.pathname === "/static/screens/login.html") event.respondWith(fetch(req).catch(() => offline()));
    return;
  }
  event.respondWith(networkFirst(req, url.pathname, isNav));
});

// 네트워크 먼저 — 받으면 보관본을 새것으로 바꾸고, 끊기면 보관본, 그것도 없으면 «연결 없음»
async function networkFirst(req, key, isNav) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === "basic") cache.put(key, res.clone()).catch(() => {});
    return res;
  } catch (e) {
    const hit = await cache.match(key);
    if (hit) return hit;
    if (isNav) return offline();
    throw e;
  }
}
function offline() {
  return new Response(OFFLINE_HTML, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } });
}
