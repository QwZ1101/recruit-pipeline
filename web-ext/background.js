// 取数放在 service worker 里做:content script 直接 fetch 本机接口会被页面同源策略拦,
// 而扩展自己的后台有 host_permissions,不受 CORS 限制。
const API = 'http://127.0.0.1:8000/api/profile'

async function getProfile() {
  const r = await fetch(API, { cache: 'no-store' })
  if (!r.ok) throw new Error(`后端返回 ${r.status}`)
  return r.json()
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === 'getProfile') {
    getProfile()
      .then(profile => sendResponse({ ok: true, profile }))
      .catch(e => sendResponse({
        ok: false,
        error: `${e.message} —— 确认台账后端在跑:python src\\api.py(只听 127.0.0.1:8000)`
      }))
    return true // 异步回复必须留通道
  }
})
