/**
 * Moka 招聘站岗位采集器 —— 只能在浏览器里跑,这不是偷懒。
 *
 * app.mokahr.com 的岗位接口(/api/outer/ats-apply/website/jobs/v2、/jobs/module)
 * 一律返回 {"data":"<一坨 base64>","necromancer":...} 这种密文,明文是它自家前端
 * JS 在浏览器里解出来的 —— 带 cookie、带 csrf 头也一样。逆向那套解密能成,但那是
 * 绕人家的反爬措施,而且对方换 key 就全废,所以这里不做。
 *
 * 本脚本只抄已经渲染到页面上的文字,和一个人翻页面看到的东西完全一样。代价是分页
 * 得跟着页面的分页器一格一格点,以及列表卡片里的 .expand-area 必须是全文(实测是)。
 *
 * 用法:
 *   1) 打开 https://app.mokahr.com/social-recruitment/<org>/<siteId>/#/jobs
 *      (校招站前缀是 /campus-recruitment/)
 *   2) F12 → Console,整段粘贴回车
 *   3) 结果写进 data/moka_raw.json —— 前提是 python src\api.py 在跑(POST 给本机后端);
 *      后端没起就只剩一份下载件(Qoder 内置浏览器连下载都不接),自己改名放进去
 *   4) python research\merge_moka.py
 *
 * 由 agent 驱动时不整段粘贴(单次工具调用 15 秒超时,采集要跑几十秒),改成:
 *   fetch 本机后端 GET /api/pool/moka.js 拿这份源码 → eval → 在同源 iframe 里
 *   window.__mokaCollect({doc, loc, download:false}) 逐站跑,结果写 window 变量再轮询。
 * 列表卡片里没有 JD 全文的站(作业帮、天数智芯)要加 {detail:true, only:'开发|算法|AI'}
 * 逐条进详情页补 —— 只补相关的,不然六十条要跑十几分钟。
 */
window.__mokaCollect = async (opts) => {
  // opts 给 agent 驱动用:在同源 iframe 里跑,DOM 和 URL 都要换成那个页面的,
  // 并且别发下载(内置浏览器会把下载丢掉,POST 到后端才是唯一落盘路)。
  // 人贴控制台时用默认值,行为跟以前一模一样。
  const doc = (opts && opts.doc) || document
  const loc = (opts && opts.loc) || location
  const m = loc.pathname.match(/^\/(social|campus)-recruitment\/([^/]+)\/(\d+)/)
  if (!m) throw new Error('URL 不是 Moka 招聘站列表页: ' + loc.pathname)
  const kind = m[1] === 'campus' ? '校招' : '社招'
  const org = m[2], siteId = m[3]

  const sleep = ms => new Promise(r => setTimeout(r, ms))
  const txt = n => (n ? n.innerText : '').replace(/\u00a0/g, ' ').trim()
  const pagerBtns = () => Array.from(doc.querySelectorAll('button[class*="Pagination-item"]'))
    .filter(b => /^[0-9]+$/.test(txt(b)))
  // \u8be6\u60c5\u9875\u6b63\u6587\u7684\u53d6\u6cd5:\u4ece\u300c\u804c\u4f4d\u63cf\u8ff0\u300d\u8fd9\u7c7b\u5c0f\u6807\u9898\u8d77,\u780d\u6389\u9875\u811a(\u5404\u5bb6\u6a21\u677f\u540c\u4e00\u5957 Moka,
  // \u4f46\u9875\u811a\u662f\u81ea\u5bb6\u6587\u6848,\u6240\u4ee5\u53ea\u6309\u5907\u6848\u53f7/\u9690\u79c1\u653f\u7b56\u8fd9\u7c7b\u901a\u7528\u6807\u8bb0\u5207)\u3002
  const JD_HEAD = /(\u804c\u4f4d\u63cf\u8ff0|\u5c97\u4f4d\u804c\u8d23|\u5de5\u4f5c\u804c\u8d23|\u804c\u4f4d\u804c\u8d23|\u5de5\u4f5c\u5185\u5bb9|\u5c97\u4f4d\u63cf\u8ff0)/
  const FOOT = /(\u4eac\u516c\u7f51\u5b89\u5907|ICP\u5907|\u9690\u79c1\u653f\u7b56|[Cc]ookies|Copyright|\u00a9|\u5173\u6ce8\u6211\u4eec)/
  const detailJd = t => {
    let s = t
    const h = s.search(JD_HEAD)
    if (h > 0) s = s.slice(h)
    const f = s.search(FOOT)
    if (f > 20) s = s.slice(0, f)
    return s.replace(/\u00a0/g, ' ').trim()
  }

  // 一张卡片 = 一个岗位。标题/职能+城市/JD 全文分在三个固定子节点里
  const grab = () => Array.from(doc.querySelectorAll('[class*="card-content"]')).map(c => {
    const a = c.closest('a')
    const href = a ? (a.getAttribute('href') || '') : ''
    return {
      id: (href.split('/job/')[1] || '').split('?')[0],
      title: txt(c.querySelector('[class*="sd-Spacing-spacing-inline"]')),
      info: txt(c.querySelector('[class*="info-"]')),
      jd: txt(c.querySelector('[class*="expand-area"]')),
    }
  }).filter(j => j.id)

  const total = Number((doc.body.innerText.match(/([0-9]+)\s*结果/) || [0, '0'])[1])
  // 这是个 SPA,刚进来卡片还没渲染出来;不等一下会当成"0 条岗位"采完收工
  for (let i = 0; i < 40 && !grab().length; i++) await sleep(250)
  const byId = {}
  let page = 1
  for (;;) {
    const cards = grab()
    cards.forEach(j => { if (!byId[j.id]) byId[j.id] = j })
    page += 1
    const next = pagerBtns().find(b => Number(txt(b)) === page)
    if (!next || Object.keys(byId).length >= total) break
    const firstOld = cards.length ? cards[0].id : ''
    next.click()
    // 点完必须等内容真换掉再抄,否则会把上一页的卡片重复计一遍、还会以为翻完了
    for (let i = 0; i < 40; i++) {
      await sleep(250)
      const now = grab()
      if (now.length && now[0].id !== firstOld) break
    }
  }

  const jobs = Object.values(byId)

  // 详情兜底:不是每家都把 JD 全文放在列表卡片里(作业帮、天数智芯的 .expand-area 只有
  // 四个字)。opts.detail 给那些空壳的逐条进详情页补抄 —— 只补标题命中 opts.only 的,
  // 否则六十条岗会把浏览器钉住十几分钟。人贴控制台时不带 opts,行为和以前一样。
  let detailed = 0
  if (opts && opts.detail) {
    const only = opts.only ? new RegExp(opts.only) : null
    const win = doc.defaultView
    const need = jobs.filter(j => j.jd.length < 80 && (!only || only.test(j.title)))
    for (const j of need) {
      win.location.hash = '#/job/' + j.id
      let t = ''
      for (let i = 0; i < 30; i++) {
        await sleep(250)
        t = doc.body ? doc.body.innerText : ''
        if (t.length > 300) break
      }
      const d = detailJd(t)
      if (d.length > j.jd.length) { j.jd = d; detailed += 1 }
    }
  }

  const out = {
    org: org, siteId: siteId, kind: kind,
    collectedAt: new Date().toISOString(), siteTotal: total, count: jobs.length,
    jobs: jobs.map(j => Object.assign(j, {
      url: 'https://app.mokahr.com' + loc.pathname + '/#/job/' + j.id
    })),
  }
  let fname = null
  if (!(opts && opts.download === false)) {
    // 人手粘贴时留一份下载件兜底;agent 驱动时内置浏览器会静默丢掉下载,不发免得看着像成功
    const blob = new Blob([JSON.stringify(out, null, 1)], { type: 'application/json' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = fname = 'moka_' + org + '_' + siteId + '_' + out.collectedAt.slice(0, 10) + '.json'
    link.click()
  }

  // 落盘两条路:后端在跑就直投 data/moka_raw.json;没跑就只有一份下载件
  // (Qoder 内置浏览器不接下载,所以由 agent 驱动时必须开着 python src\api.py)。
  // no-cors + text/plain 是"简单请求",不发预检,页面是 https 也允许打本机回环。
  let posted = false
  try {
    await fetch('http://127.0.0.1:8000/api/pool/moka', {
      method: 'POST', mode: 'no-cors', headers: { 'content-type': 'text/plain' },
      body: JSON.stringify(out),
    })
    posted = true
  } catch (e) { posted = false }

  // 自检:JD 短成这样说明 .expand-area 没渲染出来,采回去的是空壳,必须吵出来
  const thin = jobs.filter(j => j.jd.length < 80).length
  if (jobs.length < total) console.warn('⚠ 只采到 ' + jobs.length + '/' + total + ' 条,分页没点动 —— 这不算岗位下架')
  if (thin) console.warn('⚠ ' + thin + ' 条 JD 正文几乎是空的' +
    (opts && opts.detail ? '(已进过详情页还是空)' : '(列表卡片里没有全文,加 opts.detail 逐条补)'))
  if (!posted) console.warn('⚠ 没写进后端(127.0.0.1:8000 没起?),下载件也没发' + (fname ? ',只剩 ' + fname : ''))
  return { org, siteId, kind, siteTotal: total, collected: jobs.length, thinJd: thin,
           detailed: detailed, postedToBackend: posted, file: fname }
}

if (!window.__MOKA_NO_AUTORUN__) {
  // 结果写到 window.__MOKA_RESULT / __MOKA_ERROR 而不是只 console.log:
  // 由 agent 驱动时,整段贴进控制台那次调用不能 await(几十秒会被工具超时砍断),
  // 只能让它后台跑完,再另发一次小调用去读这两个变量。人肉用还是看控制台输出。
  window.__MOKA_RESULT = null; window.__MOKA_ERROR = null
  window.__mokaCollect().then(r => { window.__MOKA_RESULT = r; console.log('Moka 采集完成:', r) })
    .catch(e => { window.__MOKA_ERROR = String(e); console.error('Moka 采集失败:', e) })
}
