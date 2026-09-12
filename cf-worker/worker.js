/**
 * Cloudflare Worker: proxy Google OAuth endpoints ให้ VPS ที่ block outbound ไป Google
 *
 * Route ที่รองรับ:
 *   POST /token          → https://oauth2.googleapis.com/token
 *   GET  /v1/userinfo    → https://openidconnect.googleapis.com/v1/userinfo
 *   GET  /oauth2/v3/certs → https://www.googleapis.com/oauth2/v3/certs
 */

const ROUTES = {
  "/token": "https://oauth2.googleapis.com/token",
  "/v1/userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
  "/oauth2/v3/certs": "https://www.googleapis.com/oauth2/v3/certs",
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const upstream = ROUTES[url.pathname];

    if (!upstream) {
      return new Response("Not found", { status: 404 });
    }

    const proxyReq = new Request(upstream + url.search, {
      method: request.method,
      headers: request.headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
    });

    const resp = await fetch(proxyReq);

    // copy headers แต่เปลี่ยน CORS ให้ caller เข้าถึงได้
    const respHeaders = new Headers(resp.headers);
    respHeaders.set("Access-Control-Allow-Origin", "*");

    return new Response(resp.body, {
      status: resp.status,
      headers: respHeaders,
    });
  },
};
