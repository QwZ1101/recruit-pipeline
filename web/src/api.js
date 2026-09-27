// 前端唯一出口。规则(能流转到哪些状态)在后端,这里不判。
async function req(method, url, body) {
  const r = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(j.detail || 'HTTP ' + r.status)
  return j
}

export const api = {
  pool: () => req('GET', '/api/pool'),
  setStatus: (key, p) => req('PATCH', `/api/apps/${encodeURIComponent(key)}`, p),
  note: (key, text) => req('POST', `/api/apps/${encodeURIComponent(key)}/note`, { text }),
  sync: (p) => req('POST', '/api/sync', p || {}),
}
