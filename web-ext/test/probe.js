// 只读探针 v3:在真实投递页 F12 → Console 粘贴本文件全文回车。
// 不写任何字段、不点任何按钮。**不依赖扩展内部对象** —— content script 跑在 isolated world,
// 控制台默认是页面主世界,拿不到 window.__autofill(上一版探针就是这么误报"扩展没注入"的)。
// v2 回答了"标签在第几层";v3 要回答的是 🔒 那三个(出生日期/民族/籍贯):
// ① 那一行里除了看得见的 readonly 显示框,还藏着不能读写的真 input 吗;
// ② 弹层(选项列表)在不在主框 DOM 里 —— 不在就得点开才有选项,那只能手选或"点开再点选项"。
(() => {
  const NAMES = ['出生日期', '民族', '籍贯', '政治面貌', '最高学位', '最高学历',
                 '现居住地', '户口性质', '内推码', '应届', '毕业时间']
  const rows = [...document.querySelectorAll('[class*="form-item"]')]
    .filter(r => r.querySelector(':scope > [class*="title"]'))
  const css = el => {
    const s = getComputedStyle(el)
    return `display=${s.display} visibility=${s.visibility} ${s.width}x${s.height} opacity=${s.opacity} pos=${s.position}`
  }
  const desc = c => `<${c.tagName.toLowerCase()} type=${c.type || '-'} 只读=${c.readOnly} 禁用=${c.disabled} ` +
    `值="${(c.value || '').slice(0, 12)}" 占位="${(c.placeholder || '').slice(0, 6)}" ` +
    `class="${(c.className || '').slice(0, 40)}">`
  const out = [`主框控件总数 ${document.querySelectorAll('input,select,textarea').length}` +
               ` · iframe ${document.querySelectorAll('iframe').length}` +
               ` · open shadow ${[...document.querySelectorAll('*')].filter(e => e.shadowRoot).length}`]

  for (const r of rows) {
    const title = r.querySelector(':scope > [class*="title"]').textContent.replace(/\s+/g, '').slice(0, 12)
    if (!title || !NAMES.some(n => title.includes(n))) continue
    const ctrls = [...r.querySelectorAll('input, select, textarea')]
    const hid = ctrls.filter(c => c.offsetParent === null && !c.getClientRects().length)
    out.push(`\n【${title}】控件 ${ctrls.length} 个,其中不可见 ${hid.length} 个`)
    if (!ctrls.length) { out.push('  ↑ 整行没有 input:纯 div 假控件'); continue }
    for (const c of ctrls) {
      let d = 0, p = c
      while (p && p !== r) { p = p.parentElement; d++ }
      out.push(`  ${desc(c)}\n     ${css(c)} 可见=${c.offsetParent ? '是' : '否'} 距行=${d}层`)
    }
    // 这一行自己的子树里有没有"像弹层"的容器(北森的选项列表通常挂在这里或 body 下)
    const layers = [...r.querySelectorAll('[class*="layer"], [class*="popup"], [class*="dropdown"], [class*="picker"], [class*="option"]')]
      .filter(e => !e.querySelector('input,select,textarea'))
    out.push(`  行内弹层容器 ${layers.length} 个:` +
             (layers.slice(0, 4).map(e => `${(e.className || '').split(' ')[0]}[${e.querySelectorAll('*').length}个节点,` +
               `选项文案="${[...e.children].map(x => x.textContent.trim()).filter(Boolean).slice(0, 4).join('/') || '空'}"]`).join(' ') || '无'))
  }
  // 全局兜底:页面里挂在外面的下拉面板(点了才渲染的那种,通常 class 带 dropdown/popup)
  const pops = [...document.querySelectorAll('body > [class*="dropdown"], body > [class*="popup"], body > [class*="picker"], body > [class*="layer"]')]
  out.push(`\n挂在 body 下的弹层 ${pops.length} 个:` +
           (pops.slice(0, 6).map(e => `${(e.className || '').split(' ')[0]}(${e.offsetParent ? '显示中' : '已隐藏'},` +
             `选项 ${e.querySelectorAll('li,[class*="option"],[class*="item"]').length} 个)`).join(' ') || '无'))
  const text = out.join('\n')
  console.log(text)
  try { copy(text); console.log('>>> 已复制到剪贴板,直接粘回对话') }
  catch (e) { console.log('>>> 复制失败,手动选中上面的输出复制') }
  return `扫了 ${rows.length} 行`
})()
