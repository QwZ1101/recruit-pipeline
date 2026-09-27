// 北森投递表单自动填充。硬约束:只填输入控件,绝不点任何按钮/提交,绝不碰验证码。
(() => {
  // all_frames 会在每个 iframe 里都注入一次。顶层照旧一定有按钮;
  // 子框只有"看起来像表单"才挂,免得一个页面冒出好几个按钮
  if (window !== window.top
      && document.querySelectorAll('input, select, textarea').length < 3) return

  const ALIAS = {
    '姓名': 'name', '真实姓名': 'name', '中文名': 'name',
    '性别': 'gender', '民族': 'nation', '出生日期': 'birthday', '生日': 'birthday',
    // 紧急联系人必须是**别人**。它包含「联系电话」这个别名,靠下面 KEYS 的
    // 长别名优先才没被抢走 —— 实测漏了这几条时,扩展把申请人自己的号码填成了紧急电话
    '紧急联系人': 'emergency_contact', '紧急联系电话': 'emergency_phone',
    '紧急联系人电话': 'emergency_phone', '紧急联系方式': 'emergency_phone',
    '内推码': 'referral_code', '推荐码': 'referral_code', '内推人': 'referral_code',
    '手机号码': 'phone', '手机号': 'phone', '联系电话': 'phone', '手机': 'phone', '电话': 'phone',
    '电子邮箱': 'email', '邮箱': 'email', '电子邮件': 'email', 'email': 'email',
    '证件号码': 'id_number', '证件号': 'id_number', '身份证号': 'id_number',
    // 故意不写裸的「证件」:它命中的是「最高学位/证件照/证件有效期」这一整类说法,
    // 而证件照是上传框 —— 实测就是它差点被当成证件类型去点选项
    '证件类型': 'id_type',
    '政治面貌': 'politics', '身高': 'height', '体重': 'weight',
    '户口性质': 'hukou_nature', '户口所在地': 'hukou_location',
    '户籍所在地': 'hukou_location', '户籍': 'hukou_location',
    '籍贯': '@cascader', '生源所在地': '@cascader', '生源地': '@cascader',
    '现居住地': 'current_city', '常住城市': 'current_city', '现居住城市': 'current_city',
    '期望职位': 'target_role', '求职意向': 'target_role', '应聘岗位': 'target_role',
    '意向职位': 'target_role', '期望从事职业': 'target_role',
    '期望从事行业': 'target_industry',
    '毕业院校': 'school', '毕业学校': 'school', '学校': 'school', '就读学校': 'school',
    '院校名称': 'school', '学校名称': 'school',
    // 学院名称 ≠ 院校名称。前者是「信息工程学院」这种院系,profile 里没有,留 null 手填
    '学院名称': 'college',
    '最高学历': 'degree', '学历': 'degree', '文化程度': 'degree',
    // 学位和学历是两个答案:学历填「本科」,学位填「学士/无」。混成一个键会把「本科」
    // 塞进学位下拉,而选项里根本没有「本科」
    '最高学位': 'degree_type', '获得学位': 'degree_type', '学位': 'degree_type',
    '学习形式': 'study_mode', '学习类型': 'study_mode',
    '所学专业': 'major', '专业名称': 'major', '专业': 'major',
    '专业排名': 'class_rank', '年级排名': 'class_rank', '班级排名': 'class_rank',
    '毕业时间': 'edu_end', '毕业年份': 'edu_end', '入学时间': 'edu_start',
    '是否应届': 'is_fresh', '应届/往届': 'fresh_type', '应届': 'is_fresh',
    '求职类型': 'job_type', '工作类型': 'job_type',
    '到岗时间': 'available_date', '期望入职时间': 'available_date',
    '期望工作地': 'target_city', '期望城市': 'target_city',
    '意向城市': 'target_city', '工作城市': 'target_city',
    '期望月薪': 'expected_salary', '月薪': 'expected_salary',
    '期望薪资': 'expected_salary', '薪资要求': 'expected_salary',
    '个人作品': 'portfolio', '作品集': 'portfolio', '作品链接': 'portfolio',
    '个人主页': 'portfolio', 'github': 'github', '技术博客': 'blog', '博客': 'blog',
    '自我评价': 'self_summary', '个人总结': 'self_summary', '自我介绍': 'self_summary',
    // 真实页 2026-09-26 出现「招聘信息获取渠道」:它是正经单选(公司官网/内推/宣讲会…),
    // 认不出来就会掉进 🚫 那份"开发者待办"里。给它键、留 null,让它进 ⚠️ 让人去补答案
    '招聘信息获取渠道': 'hear_about', '获取渠道': 'hear_about',
    '招聘渠道': 'hear_about', '信息来源': 'hear_about', '了解到': 'hear_about',
  }
  // 这些词出现在 label 里就跳过——填错或触发风控的代价远高于省一次点击。
  // 照片/上传/附件 这一类是文件上传框:往里面塞值没有意义(浏览器也不允许脚本给
  // file input 赋值),而它的假控件版本很容易被当成下拉去点。
  // 「证件照」不含「照片」二字,必须单独列 —— 实测它带着"身份证"三个字,
  // 差点被当成证件类型去点选项。
  const BLOCK = ['验证码', 'captcha', '密码', 'password', '签名', 'token', '短信',
                 '照片', '证件照', '上传', '附件', '头像', '免冠', '一寸', '二寸', '2寸']
  // 长别名优先,否则「专业排名」会被「专业」抢先命中
  const KEYS = Object.keys(ALIAS).sort((a, b) => b.length - a.length)

  const norm = s => (s || '').replace(/[\s*＊:：()（）\[\]【】]/g, '')
    .replace(/请输入|请选择|必填|厘米|公斤|kg/gi, '').trim().toLowerCase()

  const isBlocked = t => BLOCK.some(b => norm(t).includes(norm(b)))
  // 控件自身的这些属性拼起来当"疑似用途"文本:验证码/密码框靠它们就能认出来,
  // 不用等 label 匹配——label 匹配是"要不要填",这里是"绝对不能填"
  const selfText = el => [el.placeholder, el.name, el.id, el.type,
    el.getAttribute('aria-label'), el.className].join(' ')

  function labelCandidates(el) {
    const out = []
    // 只接受"看起来像标签"的节点。带控件的兄弟节点是上一行的容器,
    // 拿它的整段文本会让上一行的标签串到这一行来(实测把学校名填进过验证码框)
    const push = (txt, node) => {
      if (!txt) return
      if (node && node.querySelector && node.querySelector('input,select,textarea')) return
      out.push(txt)
    }
    const aria = el.getAttribute('aria-label')
    if (aria) out.push(aria)
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`)
      if (l) out.push(l.textContent)
    }
    let n = el
    // 爬 12 层:实测北森 phoenix-select 的真 input 距 .form-item 有 **9 层**
    // (unmodeled-layer 套了 5 层壳),上限 8 会刚好卡在 .form-item__control 外面一层。
    // 上限放宽的安全由下面的护栏兜着:某层容器里控件超过 3 个就说明已经爬出行外,
    // 再往上取到的文本全是别的字段的标签 —— 那才是真正会填错行的方向。
    for (let i = 0; i < 12 && n; i++) {
      if (n.querySelectorAll('input, select, textarea').length > 3) break
      const lab = n.querySelector && n.querySelector(
        ':scope > label, :scope > .label, :scope > [class*="label"], ' +
        ':scope > [class*="title"], :scope > .form-label, :scope > .field-label')
      if (lab && !lab.contains(el)) push(lab.textContent, lab)
      const s = n.previousElementSibling
      if (s && !s.contains(el)) push(s.textContent, s)
      n = n.parentElement
    }
    push(el.placeholder), push(el.name), push(el.id), push(el.title)
    return out.filter(Boolean)
  }

  function matchField(el) {
    for (const raw of labelCandidates(el)) {
      const t = norm(raw)
      if (!t || t.length > 14) continue
      // 命中黑名单 = 这个字段整个放弃。不能退到下一个候选标签,
      // 否则"短信验证码"被拒后又会拿上一行的标签来填它
      if (isBlocked(t)) return null
      for (const k of KEYS) if (t.includes(norm(k))) return { key: ALIAS[k], label: raw.trim() }
    }
    return null
  }

  function setNative(el, val) {
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
      : el.type === 'checkbox' ? HTMLInputElement.prototype : HTMLInputElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
  }

  // 能塞字符串的控件类型。刻意不含 hidden:框架自己管理的一堆隐藏域存的是 id/token,
  // 覆盖成简历文本会静默污染提交体,比不填坏得多。
  const WRITABLE = new Set(['text', 'tel', 'number', 'search', ''])
  const visible = el => el.offsetParent !== null || el.getClientRects().length > 0

  // 整行没有一个 input/select/textarea 的假控件(实测:性别、应届/往届)。
  // 用户 2026-09-25 放开的范围:**只点单选和普通下拉的选项**,省市区级联不点,
  // 提交/下一步/验证码永远不点。所以这里只认"文案与答案完全相等"的叶子节点:
  // 相等才点,找不到就什么都不点 —— 半匹配会把旁边弹层的别的项点掉。
  function divRowChoose(row, want) {
    const leaves = [...row.querySelectorAll('*')].filter(n =>
      !n.children.length && visible(n) && !n.closest('button, a, [class*="submit"]'))
    const hit = leaves.find(n => norm(n.textContent) === norm(want))
    if (!hit) return false
    hit.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
    hit.classList.add('af-filled')
    return true
  }

  // 假控件行:标题和控件平级,标题在 form-item__title 里
  const ROW_SEL = '[class*="form-item"], [class*="field"], tr, li'
  function rowTitle(row) {
    const tn = row.querySelector(':scope > [class*="title"], :scope > label, :scope > .label')
    return tn && !tn.querySelector('input, select, textarea') ? tn : null
  }

  // 同一行里"能写"的那个控件:非只读、非禁用、不超过 3 个(再多就是爬到表格/子表里了)
  function writableSibling(el) {
    const row = el.closest(ROW_SEL) || el.parentElement
    if (!row) return null
    const sis = [...row.querySelectorAll('input, select, textarea')].filter(e =>
      !e.readOnly && !e.disabled && WRITABLE.has((e.type || '').toLowerCase()))
    if (!sis.length || sis.length > 3) return null
    return sis.find(e => !String(e.value || '').trim()) || sis[0]
  }

  // 同一行里的**原生 select**,而且它真的有这个答案对应的 option。
  // 有些表单把自定义显示框(只读)和原生 select 放在一起,前者只管渲染、后者才存值;
  // 点不开弹层时改它是比往只读框里写 value 更有效的一条路(它认 change)。
  // 护栏:一行里 select 超过 3 个说明爬到子表了,整行放弃;选项文案必须正好等于答案。
  function siblingSelect(el, val) {
    const row = el.closest(ROW_SEL) || el.parentElement
    if (!row) return null
    const sels = [...row.querySelectorAll('select')].filter(s => !s.disabled)
    if (!sels.length || sels.length > 3) return null
    for (const s of sels) {
      const o = [...s.options].filter(x => norm(x.textContent))
        .find(x => norm(x.textContent) === norm(val))
      if (!o) continue
      o.selected = true
      s.dispatchEvent(new Event('change', { bubbles: true }))
      return s
    }
    return null
  }

  // ── 弹层驱动 v2:用「可见性快照差分」认弹层,不猜 class ──────────────────
  // 上一版靠 class 名(dropdown / picker / cascader / overlay…)去找弹层容器,
  // 真实北森页上**一个都没命中** —— 8 个下拉/日期字段全报「弹层没点到选项」,
  // 而夹具全绿(假组件是我照着自己对弹层的想象捏的,当然顺着我的猜法走)。
  // 它家弹层壳叫什么我们并不知道,接着猜 class 只是第二轮瞎猜。这一版换成
  // 与实现无关的判据:点之前把页面上**所有可见元素**记成一个集合,点之后只看
  // 「哪些元素是新出现的」。护栏因此比原来更强 —— 只点因为自己这一次点击才
  // 冒出来的节点(页面别处早就渲染好的同名文案永远点不到),
  // 同时连弹层长什么样都不需要知道。
  const tick = (ms = 80) => new Promise(r => setTimeout(r, ms))

  function fire(el, type, down) {
    const Ctor = type.startsWith('pointer') && window.PointerEvent ? window.PointerEvent : MouseEvent
    try {
      el.dispatchEvent(new Ctor(type, {
        bubbles: true, cancelable: true, view: window, composed: true, button: 0,
        buttons: down ? 1 : 0, pointerId: 1, isPrimary: true,
      }))
    } catch (e) {}
  }
  // 一次「点」要按真实鼠标的顺序发。上一版只发 mousedown/mouseup/click,少了 pointer*
  // 和 focus —— 而夹具的假组件恰好只听 click,所以测试全绿、真实页却可能根本没被点着
  function tap(el) {
    if (!el) return
    try { el.focus && el.focus({ preventScroll: true }) } catch (e) {}
    for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'])
      fire(el, type, type === 'pointerdown' || type === 'mousedown')
  }
  // 只按下不松开:有的组件 pointerdown 就开面板,而 click 会把它再收回去。
  // 完整点击失败后在同一个热区上补试这一种,才分得清"点不开"和"点开又关掉"
  function press(el) {
    if (!el) return
    try { el.focus && el.focus({ preventScroll: true }) } catch (e) {}
    fire(el, 'pointerdown', true); fire(el, 'mousedown', true)
  }
  const dismiss = el => el.dispatchEvent(
    new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))

  // 扩展自己的面板要排除,不然每次渲染报告都会被判成「新出现的弹层」
  const isMine = el => el.closest('#af-report, #af-btn')
  function visibleAll() {
    const s = new Set()
    for (const el of document.body.querySelectorAll('*')) {
      if (!isMine(el) && visible(el)) s.add(el)
    }
    return s
  }
  // 新出现节点里最靠上的那几个:父节点不是新出现的(它本来就可见,或者压根不在扫描范围里)。
  // 面板整块 display:none→block 时得到的是面板本体;只有格子是新节点时得到一堆格子。
  function freshRoots(before, after) {
    const tops = []
    for (const el of after) {
      if (before.has(el)) continue
      const p = el.parentElement
      if (p && after.has(p) && !before.has(p)) continue
      tops.push(el)
    }
    return tops
  }
  const clickOk = n => !n.closest('[class*="submit"], button[type="submit"], a[href^="http"]')
  // 新出现的**叶子**节点。弹层里的选项一定是叶子(或者叶子里就是那几个字),
  // 拿它们当候选意味着:没点开的东西、别的字段的常驻文案,都进不了候选集
  function freshLeaves(before, after) {
    const out = []
    for (const n of after) {
      if (before.has(n) || n.children.length) continue
      if (!(n.textContent || '').trim() || !clickOk(n)) continue
      out.push(n)
    }
    return out
  }
  const texts = ns => ns.map(n => (n.textContent || '').trim()).filter(Boolean)

  // 给日期/级联找一个"装得下整块面板"的容器:取新根节点里叶子最多的那个;
  // 一个都不够格(面板壳常驻、只有里面的格子是新节点)就退到「拥有最多新根节点的父节点」
  function pickBox(roots, leaves, test) {
    const score = b => leaves.reduce((k, n) => k + (b.contains(n) ? 1 : 0), 0)
    for (const c of [...roots].sort((a, b) => score(b) - score(a))) {
      if (!test || test(c)) return c
    }
    const cnt = new Map()
    for (const t of roots) {
      const p = t.parentElement
      if (p) cnt.set(p, (cnt.get(p) || 0) + 1)
    }
    const par = [...cnt.entries()].sort((a, b) => b[1] - a[1])[0]
    if (par && par[1] >= 3 && (!test || test(par[0]))) return par[0]
    return null
  }

  // 点击热区候选:input 本身、它的组件壳、壳的上一层。
  // **只试这几处** —— 再往上就是整行/整个表单,一点就会点开别字段的弹层
  function hotzones(el) {
    const out = []
    const add = n => { if (n && n !== document.body && !out.includes(n)) out.push(n) }
    add(el)
    const shell = el.closest('[class*="select"], [class*="picker"], [class*="cascader"], ' +
      '[class*="input"], [class*="date"], [role="combobox"]')
    add(shell)
    add(el.parentElement)
    add(shell && shell.parentElement)
    return out.slice(0, 4)
  }

  // 弹层是异步渲染的,动画各家不一样:先给它一帧,再轮询"有没有新节点",最多 260ms。
  // 比固定 sleep 既快(瞬间出来的组件不用白等)又稳(慢动画有预算)
  async function waitGrown(snap, budget = 260) {
    await tick(20)
    const t0 = Date.now()
    for (;;) {
      const after = visibleAll()
      const roots = freshRoots(snap, after)
      if (roots.length) return { after, roots }
      if (Date.now() - t0 > budget) return null
      await tick(60)
    }
  }

  // 点开这个字段的弹层。test 用来挑特定面板(日历要认「xxxx年」),不传就是任意弹层。
  // 失败时把每个热区各试出什么压成**一行**写进 notes —— 这是面板能自证的地方:
  // 下一张截图我就能看到它家弹层到底开没开、里面的选项叫什么,而不是再来一轮瞎猜
  async function openLayer(el, notes, label, test) {
    const hs = hotzones(el)
    const steps = []
    for (let i = 0; i < hs.length; i++) {
      // 两种按法:完整点一次;只按下不松开(有的组件 pointerdown 就开、click 又把它收回)
      for (const seq of [tap, press]) {
        const before = visibleAll()
        seq(hs[i])
        const g = await waitGrown(before, seq === press ? 150 : 260)
        if (!g) { steps.push(`热区${i + 1}${seq === press ? '按下' : '点击'}没开`); dismiss(el); continue }
        const leaves = freshLeaves(before, g.after)
        const box = pickBox(g.roots, leaves, test)
        const smp = texts(leaves.slice(0, 6)).join('|')
        if (test && !box) { steps.push(`热区${i + 1}开的不是面板(${smp})`); dismiss(el); continue }
        if (leaves.length < 2) {
          steps.push(`热区${i + 1}只冒出${leaves.length}段字(${smp})`)
          dismiss(el); continue
        }
        return { before, after: g.after, roots: g.roots, box, leaves, zone: i + 1 }
      }
    }
    notes.push(`${label}:${steps.join(';')}——一个节点都没点`)
    return null
  }

  async function openChoose(el, want, notes, label) {
    const op = await openLayer(el, notes, label)
    if (!op) return false
    const w = optNorm(want)
    const hit = op.leaves.find(n => optNorm(n.textContent) === w)
    if (!hit) {
      notes.push(`${label}:弹层里没有「${want}」,它给的是「${texts(op.leaves.slice(0, 10)).join('、')}」`)
      dismiss(el)
      return false
    }
    tap(hit)
    await tick()
    dismiss(el)
    return true
  }

  const ymRe = /^(\d{4})年(\d{1,2})月$/
  const flat = n => (n.textContent || '').replace(/\s+/g, '')
  const ymOf = panel => {
    const m = flat(panel).match(/(\d{4})年(\d{1,2})月/)
    return m ? +m[1] * 12 + (+m[2]) : null
  }
  const yearOf = panel => {
    const m = flat(panel).match(/\d{4}/)
    return m ? +m[0] : null
  }
  const monthCells = panel => [...panel.querySelectorAll('*')].filter(n =>
    !n.children.length && visible(n) && clickOk(n) && /^\d{1,2}月$/.test(flat(n)))
  // 一个节点"是谁",报错时要能一眼看出点错了什么(2026-09-26 那次探测翻页按钮,
  // 实测位移全是 0 而出生日期被写成了 2004-01-01 —— 就是点到了日历的日格,
  // 光看"位移:0,0,0"根本不知道那八个候选是哪些节点)。
  const who = n => {
    const cls = String(n.className || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).join('.')
    return `${n.tagName.toLowerCase()}${cls ? '.' + cls : ''}「${flat(n).slice(0, 6)}」`
  }

  // 抬头旁的翻页按钮。**用几何筛,不用"长得像不像按钮"筛**:
  // 真实页(2026-09-26 16:15 截图)报 `按钮实测位移:0,0,0,0,0,0,0,0`,而出生日期被写成了
  // 2004-01-01 —— 那 8 个"按钮"里有**日历的日格**(空白格/数字格文字都很短,按文字判据全像按钮),
  // 点中一格等于替用户选了一天,抬头当然一动不动。
  // 现在只认**和抬头在同一条横线(同一横带)上的小节点**:日格、星期表头、「今天」「本月」
  // 都在抬头下面,一律进不来。
  function navCands(panel) {
    const head = [...panel.querySelectorAll('*')]
      .filter(n => ymRe.test(flat(n)) || /^\d{4}$/.test(flat(n))).pop()
    const cands = []
    if (!head) return { head: null, cands }
    const hr = head.getBoundingClientRect()
    if (!hr.width || !hr.height) return { head, cands }
    for (const n of panel.querySelectorAll('*')) {
      if (n === head || !visible(n) || !clickOk(n)) continue
      if (n.contains(head) || head.contains(n)) continue
      const t = flat(n)
      if (t.length > 2 || /\d|今天|此刻|现在|选择|本月/.test(t)) continue
      if ([...n.querySelectorAll('*')].some(c => flat(c))) continue
      const r = n.getBoundingClientRect()
      if (!r.width || r.width > 80 || r.height > 80) continue
      // 同一横带:上下边缘和抬头重叠才算(留 4px 容差)
      if (r.bottom < hr.top - 4 || r.top > hr.bottom + 4) continue
      cands.push(n)
    }
    cands.splice(8)
    return { head, cands }
  }

  // 逐个探出每个翻页按钮让抬头走几格,再沿**当前**抬头翻到目标;每步都回读自证,
  // 没翻到目标就返回 false,调用方绝不去点格子,所以填不进错值
  async function navigate(panel, cands, curOf, target, notes, label, fmt, el) {
    const known = new Map()        // 按钮 → 点一次走几格(±1 / ±12 / NaN)
    // 护栏:翻页按钮**只该让抬头动**,不该让值动。真实页上"候选"里混进了日历的日格,
    // 点一下等于替用户选了一天(2026-09-26 出生日期被写成 2004-01-01)。
    // 所以每点一次都回读 input 的原值:它一变,说明刚才那一下是"选择"不是"翻页" ——
    // 立刻停手,把改成的值报出来让人核对,绝不继续点、也绝不去点格子。
    const v0 = el ? String(el.value || '') : null
    const slipped = () => (el && v0 !== null && String(el.value || '') !== v0) ? String(el.value || '') : null
    const probe = async btn => {
      const a = curOf()
      tap(btn)
      await tick(50)
      const b = curOf()
      return (a === null || b === null) ? NaN : b - a
    }
    const fmtD = v => Number.isNaN(v) ? '不动' : (v > 0 ? '+' + v : '' + v)
    const idOf = () => cands.map(c => `${who(c)}=${fmtD(known.get(c))}`).join('、')
    for (const c of cands) {
      known.set(c, await probe(c))
      const bad = slipped()
      if (bad !== null) {
        notes.push(`${label}:探测翻页按钮时点到了${who(c)},把值改成了「${bad}」,已停手 —— 这一项请手选并核对`)
        return false
      }
    }
    const best = need => {
      let b = null
      for (const [n, dl] of known) {
        if (Math.sign(dl) !== Math.sign(need) || Math.abs(dl) > Math.abs(need)) continue
        if (!b || Math.abs(dl) > Math.abs(known.get(b))) b = n
      }
      return b
    }
    for (let guard = 0; guard < 40; guard++) {
      if (!panel.isConnected) { notes.push(`${label}:翻页时面板被换掉了`); return false }
      const cur = curOf()
      if (cur === null) { notes.push(`${label}:抬头读不出年月了`); return false }
      const need = target - cur
      if (!need) return true
      const btn = best(need)
      if (!btn) {
        notes.push(`${label}:翻不到${fmt(target)}(现在${fmt(cur)})。按钮实测位移:${idOf() || '无'}`)
        return false
      }
      await probe(btn)
      const bad = slipped()
      if (bad !== null) {
        notes.push(`${label}:翻页时点${who(btn)}把值改成了「${bad}」,已停手 —— 这一项请手选并核对`)
        return false
      }
    }
    notes.push(`${label}:翻页超过上限,没到${fmt(target)}`)
    return false
  }

  async function openDate(el, want, notes, label) {
    const g = String(want).match(/(\d{4})\D(\d{1,2})\D(\d{1,2})/)
    if (!g) return false
    const [, y, mo, d] = g.map(Number)
    const op = await openLayer(el, notes, label, b => /\d{4}年\d{1,2}月/.test(flat(b)))
    if (!op || !op.box) return false
    const panel = op.box
    const { head, cands } = navCands(panel)
    if (!cands.length) {
      notes.push(`${label}:抬头「${flat(head || panel)}」旁边一个翻页按钮都没找到,没乱点`)
      dismiss(el); return false
    }
    const fmt = c => `${Math.floor((c - 1) / 12)}年${((c - 1) % 12) + 1}月`
    const okNav = await navigate(panel, cands, () => ymOf(panel), y * 12 + mo, notes, label, fmt, el)
    if (!okNav) { dismiss(el); return false }
    const cell = [...panel.querySelectorAll('*')].find(n => !n.children.length && visible(n)
      && n.textContent.trim() === String(d) && clickOk(n) && !op.before.has(n)
      && !/disabled|prev|next|other|last|first/i.test(n.className || ''))
    if (!cell) { notes.push(`${label}:面板里找不到第${d}天的格子`); dismiss(el); return false }
    tap(cell)
    await tick()
    dismiss(el)
    return true
  }

  // 年月值(2023-09):北森给的是「年份抬头 + 12 个月格」的月面板,没有日格。
  // 用抬头旁的 « » 翻年(位移探法同 openDate),再点「X月」格;
  // 万一开出来是带日格的日历(证书获得时间那种),翻到年月后点 1 号。
  async function openMonth(el, want, notes, label) {
    const g = String(want).match(/(\d{4})\D(\d{1,2})/)
    if (!g) return false
    const [, y, mo] = g.map(Number)
    const op = await openLayer(el, notes, label, b => /\d{4}/.test(flat(b)) && /\d{1,2}月/.test(flat(b)))
    if (!op || !op.box) return false
    const panel = op.box
    const { head, cands } = navCands(panel)
    if (!cands.length) {
      notes.push(`${label}:抬头「${flat(head || panel)}」旁边一个翻页按钮都没找到,没乱点`)
      dismiss(el); return false
    }
    const isMonthPanel = monthCells(panel).length >= 12
    const curOf = isMonthPanel ? () => yearOf(panel) : () => ymOf(panel)
    const target = isMonthPanel ? y : y * 12 + mo
    const fmt = isMonthPanel ? c => `${c}年` : c => `${Math.floor((c - 1) / 12)}年${((c - 1) % 12) + 1}月`
    const okNav = await navigate(panel, cands, curOf, target, notes, label, fmt, el)
    if (!okNav) { dismiss(el); return false }
    const cell = isMonthPanel
      ? monthCells(panel).find(n => flat(n) === `${mo}月` && !op.before.has(n))
      : [...panel.querySelectorAll('*')].find(n => !n.children.length && visible(n)
          && n.textContent.trim() === '1' && clickOk(n) && !op.before.has(n)
          && !/disabled|prev|next|other|last|first/i.test(n.className || ''))
    if (!cell) {
      notes.push(`${label}:面板里找不到${isMonthPanel ? `${mo}月` : '1号'}的格子`)
      dismiss(el); return false
    }
    tap(cell)
    await tick()
    dismiss(el)
    return true
  }

  // 结束时间「至今」:弹层里没这个选项,它是行内的「至今」勾选框。
  // 真实页(2026-09-26)报「行里没找到」—— 它不一定和结束时间**在同一个 .form-item 里**
  // (北森常把它放成隔壁那个 form-item)。所以行里找不到就往**再上一层**找一次,
  // 但只在那一层里**唯一一个**「至今」时才点:子弹表一行一个「至今」,多个就没法判断归谁,
  // 宁可报出来让人自己勾。
  async function pickUntilNow(el, notes, label) {
    const row = el.closest(ROW_SEL) || el.parentElement
    const findIn = r => r && [...r.querySelectorAll('*')].filter(n =>
      !n.children.length && visible(n) && flat(n) === '至今')
    let hits = findIn(row)
    if (!hits.length) {
      hits = findIn(row && row.parentElement)
      if (hits.length > 1) {
        notes.push(`${label}:这一层里有 ${hits.length} 个「至今」,分不清归哪一行,没乱点`)
        return false
      }
    }
    if (!hits.length) { notes.push(`${label}:行里没找到「至今」勾选框,没乱点`); return false }
    const leaf = hits[0]
    const box = leaf.closest('label') || leaf.parentElement || leaf
    tap(box.querySelector('input') || box)
    await tick()
    const shown = norm(shownOf(el)) + norm(rowTextExcept(el, []))
    if (!shown.includes('至今')) {
      notes.push(`${label}:点了「至今」但行里显示「${shown.slice(0, 20) || '空'}」`)
      return false
    }
    return true
  }

  // 点完之后回读:显示框里现在到底是几个字。对不上就当没填,报出去让人手选
  function shownOf(el) {
    if ((el.value || '').trim()) return el.value
    const row = el.closest(ROW_SEL) || el.parentElement
    if (!row) return ''
    const leaf = [...row.querySelectorAll('span, em, i, div')].find(n =>
      !n.children.length && visible(n) && n.textContent.trim()
      && !n.querySelector('input') && n !== el)
    return leaf ? leaf.textContent : ''
  }

  // 行里现在看得见几个字,**排除掉 boxes(我们自己点开的那些弹层容器)里的文字**
  function rowTextExcept(el, boxes) {
    const row = el.closest(ROW_SEL) || el.parentElement
    if (!row) return ''
    return texts([...row.querySelectorAll('*')].filter(n =>
      !n.children.length && visible(n) && !boxes.some(b => b && b.contains(n)))).join('')
  }

  // 选项文案里常拖一个箭头(江西省›),而箭头可能在同一个文本节点里 —— 剥掉再比
  const optNorm = s => norm(s).replace(/[›>»／/]+$/, '')

  // 在已打开的容器里找"因为点上一级才冒出来"的那个选项。
  // freshSince 是上一次点击**之前**的可见快照:本级列表在里面是新的,
  // 上一级(已经点过了、仍然可见)不是 —— 所以不会把同一级重复点一遍
  function pickOption(boxes, freshSince, want) {
    const w = optNorm(want)
    for (const b of boxes) {
      if (!b) continue
      const hit = [...b.querySelectorAll('*')].find(n =>
        !n.children.length && visible(n) && !freshSince.has(n) && optNorm(n.textContent) === w && clickOk(n))
      if (hit) return hit
    }
    return null
  }

  // 省市区级联(用户 2026-09-26 放开到这一步):逐级点 省› 市› 区,再点**弹层内**的「确定」。
  // 这是全模块唯一允许点的按钮,护栏三条 —— ① 每一级点的都是"点上一级之后才出现的"叶子;
  // ② 它必须在弹层容器子树里;③ 文案正好是「确定」。提交/下一步在页面别处,撞不上这几条。
  async function cascaderChoose(el, parts, notes, label) {
    const op = await openLayer(el, notes, label)
    if (!op) return false
    const boxes = [op.box || op.roots[0]]
    let freshSince = op.before
    for (const want of parts) {
      const hit = pickOption(boxes, freshSince, want)
      if (!hit) {
        const inPanel = texts(boxes.filter(Boolean)
          .flatMap(b => [...b.querySelectorAll('*')].filter(n => !n.children.length && visible(n)))
          .slice(0, 10)).join('、')
        notes.push(`${label}:级联里点不到「${want}」,面板里是「${inPanel}」`)
        dismiss(el)
        return false
      }
      const snap = visibleAll()
      tap(hit)
      await tick(120)
      const grown = await waitGrown(snap)
      freshSince = snap
      if (grown) boxes.push(pickBox(grown.roots, freshLeaves(snap, grown.after)) || grown.roots[0])
    }
    const confirm = boxes.filter(Boolean).reduce((acc, b) => acc ||
      [...b.querySelectorAll('*')].find(n =>
        !n.children.length && visible(n) && !op.before.has(n) && norm(n.textContent) === '确定'), null)
    if (!confirm) {
      notes.push(`${label}:级联点完三级,弹层里没有「确定」按钮(只点过一次都不算,已放弃)`)
      dismiss(el)
      return false
    }
    tap(confirm)
    await tick(120)
    // 回读必须**把弹层自己的文字排掉**:北森的级联面板就挂在 .form-item 里面,
    // 省市区那几个名字本来就在行的文本里,不排除的话永远"看着像选中了"。
    // 反过来也不能只盯 `el.value` —— 真实页(2026-09-26)显示「示例县」的是**同行另一个 input**,
    // 我们手里这个 readonly 框一直是空的,于是选好了也报「行里现在显示空」。
    const last = optNorm(parts[parts.length - 1])
    const row = el.closest(ROW_SEL) || el.parentElement
    // 回读按**"点开弹层之前就在那儿、当时就看得见"**来认(而不是"整行去掉弹层文字"):
    // ① 面板是新长出来的节点 → 它那一堆省市区名字一个都不算(以前把面板里的「示例县」
    //    读成"已经选中了、值其实被丢弃"就是这个坑);
    // ② 真实页(2026-09-26)把选中的值写回**同行另一个 input**,我们手里这个 readonly
    //    框一直是空的 → 所以行里所有 input 的当前值也要算进来,不然选好了也报「空」。
    const had = row ? texts([...row.querySelectorAll('*')].filter(n =>
      !n.children.length && visible(n) && op.before.has(n))).join('') : ''
    const vals = row ? [...row.querySelectorAll('input, textarea')].map(i => String(i.value || '')) : []
    const shown = norm(had + ' ' + vals.join(' '))
    if (!shown.includes(last)) {
      notes.push(`${label}:三级都点了、也点了「确定」,但行里现在显示「${shown.slice(0, 26) || '空'}」`)
      dismiss(el)
      return false
    }
    return true
  }

  async function pickInto(el, val, notes, label) {
    val = String(val)
    let ok
    if (/至今/.test(val)) ok = await pickUntilNow(el, notes, label)
    else if (/(\d{4})\D(\d{1,2})\D(\d{1,2})/.test(val)) ok = await openDate(el, val, notes, label)
    else if (/(\d{4})\D(\d{1,2})/.test(val)) ok = await openMonth(el, val, notes, label)
    else ok = await openChoose(el, val, notes, label)
    if (!ok) return false
    if (/至今/.test(val)) return true
    const shown = norm(shownOf(el))
    if (shown === norm(val)) return true
    // 年月值填完显示框可能带日(2026-07-01)或写成「2026年7月」:按年月比对,值带日才比日
    const pv = val.match(/(\d{4})\D(\d{1,2})(?:\D(\d{1,2}))?/)
    const ps = shown.match(/(\d{4})\D(\d{1,2})(?:\D(\d{1,2}))?/)
    return !!(pv && ps && +pv[1] === +ps[1] && +pv[2] === +ps[2] && (!pv[3] || +pv[3] === +ps[3]))
  }

  // ── 子表(教育经历 / 项目经历 / 实习实践 / 语言 / 证书 / 获奖)──────────────
  // 这些列的标签**每个分区都出现一遍**:「开始时间」在教育经历有、项目经历也有、
  // 实习实践还有。所以别名表里绝不能写死一个键 —— 那会把教育经历的月份填进项目经历
  // (这正是以前把它们整个留给 🚫 的原因)。
  // 现在的做法:先按**分区标题**把页面切成几段(标题节点在 DOM 顺序上排在它下面所有
  // 内容之前,取"离控件最近的那个在前面的标题"),段内再按列名去 `profile.tables[分区][第几行]` 取答案。
  // 行号 = 同一列的控件在 DOM 里出现的次序(子表就是按行往下排的);
  // 页面比答案表多出来的行一律不动、也不猜。
  const SECTIONS = [
    { id: 'edu', cn: '教育经历', names: ['教育经历', '学习经历', '教育背景'], cols: {
        '开始时间': 'start', '结束时间': 'end', '入学时间': 'start', '毕业时间': 'end',
        '成绩gpa': 'gpa', 'gpa': 'gpa', '学校名称': 'school', '院校名称': 'school',
        '所学专业': 'major', '专业名称': 'major', '专业': 'major',
        '学历': 'degree', '最高学历': 'degree', '学位': 'degree_type',
        '最高学位': 'degree_type', '学习形式': 'study_mode', '院系名称': 'college',
        '学院名称': 'college', '在校期间职务': 'duty', '职务': 'duty' } },
    { id: 'intern', cn: '实习实践', names: ['实习经历', '实践经历', '实习实践', '工作经历'], cols: {
        '开始时间': 'start', '结束时间': 'end', '实践名称': 'name', '实习名称': 'name',
        '单位名称': 'org', '公司名称': 'org', '实习内容': 'content', '实践内容': 'content',
        '实践描述': 'desc', '实习描述': 'desc', '担任职位': 'duty', '职位': 'duty', '职责': 'duty' } },
    { id: 'practice', cn: '在校实践', names: ['在校实践', '校园实践', '社会实践'], cols: {
        '实践名称': 'name', '实践描述': 'desc', '专利成果': 'patent',
        '获得荣誉': 'honor', '荣誉': 'honor', '论文/专著': 'paper', '论文': 'paper',
        '专著': 'paper', '参赛经历': 'contest' } },
    { id: 'project', cn: '项目经历', names: ['项目经历', '项目经验'], cols: {
        '开始时间': 'start', '结束时间': 'end', '项目名称': 'name', '项目中职责': 'duty',
        '担任角色': 'duty', '项目成果': 'result', '项目描述': 'desc', '项目内容': 'desc' } },
    { id: 'language', cn: '语言能力', names: ['语言能力', '外语能力', '语言水平'], cols: {
        '语言类型': 'type', '语种': 'type', '语言等级': 'level', '等级': 'level',
        '听说能力': 'listening', '读写能力': 'reading' } },
    { id: 'cert', cn: '证书', names: ['证书', '资格证书', '专业技能'], cols: {
        '证书种类': 'kind', '证书名称': 'name', '获得时间': 'date', '名称': 'name' } },
    { id: 'award', cn: '获奖荣誉', names: ['获奖', '获奖情况', '荣誉', '奖励'], cols: {
        '获得荣誉': 'name', '奖项名称': 'name', '荣誉名称': 'name', '名称': 'name',
        '获得时间': 'date', '颁奖机构': 'org', '专利成果': 'patent',
        '论文/专著': 'paper', '论文': 'paper', '专著': 'paper', '参赛经历': 'contest' } },
  ]

  // 分区标题:整段文字正好等于某个分区名(北森用的是 div 不是 h 几,所以只能按文字认)。
  // 页面顶部常有一列**锚点菜单**把分区名全列一遍 —— 所以每个 id 只取第一次出现的标题,
  // 且归属规则是"前面最近的标题":锚点会被真正的分区标题盖掉。
  function headIndex() {
    const out = []
    for (const n of document.body.querySelectorAll('*')) {
      if (n.children.length || !visible(n)) continue
      const t = norm(n.textContent)
      if (!t || t.length > 10) continue
      const s = SECTIONS.find(x => x.names.some(nm => norm(nm) === t))
      if (s && !out.some(o => o.id === s.id)) out.push({ node: n, id: s.id })
    }
    return out
  }
  function sectionFor(el, heads) {
    let id = null
    for (const h of heads) {
      if (h.node === el || !(h.node.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING)) break
      id = h.id
    }
    return id
  }
  // 列名匹配:整段等于列名,或者"列名 + 不超过 3 个字"(单位后缀,如「开始时间(年)」)。
  // 不做子串匹配 —— 「开始时间」含「时间」,子串会把别的列也一起命中
  function colOf(cands, cols) {
    for (const raw of cands) {
      const t = norm(raw)
      if (!t || t.length > 14) continue
      if (cols[t]) return { key: cols[t], label: raw.trim() }
      for (const k in cols) if (t.startsWith(k) && t.length - k.length <= 3) return { key: cols[k], label: raw.trim() }
    }
    return null
  }

  // 异步是因为点弹层要等组件渲染(下一帧才有选项),不是我想在页面里做别的事
  async function fillAll(profile) {
    const rep = { filled: [], kept: [], skipped: [], cascader: [], missing: [],
                  manual: [], verify: [], clicked: [], unknown: [], debug: [] }
    const used = new Set()          // 已被某个控件认领的标签,后面据此找"漏网的字段"
    const claim = lab => used.add(norm(lab))
    const radios = {}
    // 撞不到别名、或压根不可见的 input。留着走下面那条"隐藏真控件"的路线
    const probeOnly = []
    // 撞上别名但本身只读的(=弹层显示框)。这些字段先别急着报 🔒:
    // 同一行里可能藏着一个能写的真控件,那个才是存值的地方
    const pending = []
    // 省市区级联(籍贯/生源所在地):要逐级点完再点弹层里的「确定」,单独一轮
    const cascJobs = []

    for (const el of document.querySelectorAll('input, select, textarea')) {
      if (isBlocked(selfText(el))) continue
      const type = (el.type || '').toLowerCase()
      if (['submit', 'button', 'image', 'hidden', 'file', 'password'].includes(type)) continue
      // 不可见的控件不报告、但也不能直接扔:北森把下拉的"显示框"和"真值框"分成两个,
      // 真那个往往是隐藏的。看不见 ≠ 不是它管的字段。
      if (!visible(el)) { probeOnly.push(el); continue }
      if (type === 'radio') {
        const grp = el.name || 'anon'
        ;(radios[grp] = radios[grp] || []).push(el)
        continue
      }

      const m = matchField(el)
      if (!m) { probeOnly.push(el); continue }
      claim(m.label)
      if (m.key === '@cascader') { cascJobs.push({ el, label: m.label }); continue }
      // 只读输入框 = 北森的自定义弹层(日期选择器、下拉)。往它写 value 只改显示、
      // 不改组件自己的 state,提交时按空处理。先记下来,下面看同行有没有能写的控件。
      if (el.readOnly || el.disabled) { pending.push({ el, label: m.label, key: m.key }); continue }

      // 下拉停在「请选择」等于没填,不能算已有值——否则户口性质这类字段会被悄悄跳过
      const isSelect = el.tagName === 'SELECT'
      const cur = isSelect
        ? (el.options[el.selectedIndex] ? el.options[el.selectedIndex].textContent.trim() : '')
        : (el.value || '').trim()
      const blank = isSelect ? (!cur || ['请选择', '请输入', '不限'].includes(cur)) : !cur
      if (!blank) { rep.kept.push(`${m.label}(已有「${cur}」)`); continue }

      const val = profile[m.key]
      if (val === null || val === undefined || val === '') {
        rep.missing.push(m.label)
        continue
      }
      if (isSelect) {
        // 空文案的占位 option 必须剔掉:'城镇'.includes('') 恒真,会把「请选择」当成命中
        const opts = [...el.options].filter(o => norm(o.textContent))
        const want = norm(val)
        const opt = opts.find(o => norm(o.textContent) === want)
          || opts.find(o => norm(o.textContent).includes(want) || want.includes(norm(o.textContent)))
        if (!opt) { rep.skipped.push(`${m.label}(下拉里没有「${val}」)`); continue }
        opt.selected = true
        el.dispatchEvent(new Event('change', { bubbles: true }))
      } else if (el.closest('[class*="select"], [class*="picker"], [class*="cascader"], [role="combobox"]')) {
        // 假下拉/日期:按人那条路走一遍(点开 → 点等值选项 → 回读显示框)。
        // 点中了才算填上;点不动才试同行的原生 select,再不行才"写值"——那种只能进 👀。
        if (await pickInto(el, val, rep.debug, m.label)) {
          el.classList.add('af-filled')
          rep.clicked.push(`${m.label} → ${val}`)
          continue
        }
        const sel = siblingSelect(el, val)
        if (sel) {
          el.classList.add('af-filled')
          rep.verify.push(`${m.label}(${val})· 弹层没点开,选的是同行那个原生 select`)
          continue
        }
        setNative(el, String(val))
        el.classList.add('af-filled')
        // 往 input 里写值只能算"待核实",绝不能同时进 ✅ —— 那样看着像填好了
        rep.verify.push(`${m.label}(${val})· 弹层没点到选项,值是写进去的`)
        continue
      } else {
        setNative(el, String(val))
      }
      el.classList.add('af-filled')
      rep.filled.push(m.label)
    }

    // 子表那一摊:分区 + 列名 → profile.tables。命中就从 probeOnly 里摘走,
    // 免得下面 B 路线拿同一批控件再处理一遍
    const heads = headIndex()
    if (heads.length) {
      const tables = profile.tables || {}
      const groups = new Map()
      const meta = new Map()
      const taken = new Set()
      for (const el of probeOnly) {
        if (isBlocked(selfText(el))) continue
        const ty = (el.type || '').toLowerCase()
        if (['submit', 'button', 'image', 'hidden', 'file', 'password'].includes(ty)) continue
        // 复选/单选框不参与"列 → 行"的分组:子弹表里一行的第 N 个格子才是第 N 行,
        // 而「至今」这种勾选框和结束时间**同行**,不排掉它就会被当成该列的第二行
        if (ty === 'checkbox' || ty === 'radio') continue
        const sec = sectionFor(el, heads)
        if (!sec) continue
        const S = SECTIONS.find(x => x.id === sec)
        const col = colOf(labelCandidates(el), S.cols)
        if (!col) continue
        const gk = `${sec}.${col.key}`
        if (!groups.has(gk)) groups.set(gk, [])
        groups.get(gk).push(el)
        meta.set(el, { sec, cn: S.cn, key: col.key, label: col.label })
        taken.add(el)
      }
      for (const [gk, els] of groups) {
        const [sec, key] = gk.split('.')
        const rows = tables[sec] || []
        for (let i = 0; i < els.length; i++) {
          const el = els[i]
          const mt = meta.get(el)
          const lab = `${mt.cn}·${mt.label}`
          claim(mt.label)                    // 报过名了,别再进 🚫
          const row = rows[i]
          if (!row) { rep.missing.push(`${lab}(页面第${i + 1}行,答案表里只有 ${rows.length} 行)`); continue }
          const val = row[key]
          if (val === null || val === undefined || val === '') { rep.missing.push(lab); continue }
          const cur = (el.value || '').trim()
          if (cur) { rep.kept.push(`${lab}(已有「${cur}」)`); continue }
          const isPicker = el.readOnly || el.disabled
            || el.closest('[class*="select"], [class*="picker"], [class*="cascader"], [role="combobox"]')
          if (isPicker) {
            if (await pickInto(el, val, rep.debug, lab)) {
              el.classList.add('af-filled')
              rep.clicked.push(`${lab} → ${val}`)
              continue
            }
            const s2 = siblingSelect(el, val)
            el.classList.add('af-filled')
            if (s2) rep.verify.push(`${lab}(${val})· 弹层没点开,选的是同行那个原生 select`)
            else {
              setNative(el, String(val))
              rep.verify.push(`${lab}(${val})· 弹层没点到选项,值是写进去的`)
            }
            continue
          }
          setNative(el, String(val))
          el.classList.add('af-filled')
          rep.filled.push(lab)
        }
      }
      for (let i = probeOnly.length - 1; i >= 0; i--) if (taken.has(probeOnly[i])) probeOnly.splice(i, 1)
    }

    // 单选组:整组的 label 命中别名,再点组里文案等于答案的那个选项
    for (const grp in radios) {
      const els = radios[grp]
      const m = matchField(els[0])
      if (!m || m.key === '@cascader') continue
      claim(m.label)
      const val = profile[m.key]
      if (val === null || val === undefined) { rep.missing.push(m.label); continue }
      if (els.some(e => e.checked)) { rep.kept.push(m.label + '(已选)'); continue }
      const hit = els.find(e => norm(e.value) === norm(val)
        || norm(e.nextSibling && e.nextSibling.textContent) === norm(val)
        || norm(e.parentNode.textContent) === norm(val))
      if (!hit) { rep.skipped.push(`${m.label}(没有「${val}」这个选项)`); continue }
      hit.click()
      hit.classList.add('af-filled')
      rep.filled.push(m.label)
    }
    // 省市区级联:逐级点完 → 点弹层内的「确定」→ 回读显示框里有没有最后那一级
    for (const j of cascJobs) {
      const parts = [profile.native_province, profile.native_city, profile.native_county]
        .filter(Boolean).map(String)
      if (!parts.length) { rep.missing.push(`${j.label}(省市区三级)`); continue }
      if (await cascaderChoose(j.el, parts, rep.debug, j.label)) {
        j.el.classList.add('af-filled')
        rep.clicked.push(`${j.label} → ${parts.join('/')}`)
      } else {
        rep.cascader.push(`${j.label}(点开手选:${parts.join('/')})`)
      }
    }

    // 🔒 那批:标签撞上了、但控件是只读的弹层显示框。顺序是
    // ① 点开弹层点等值选项(点中且回读对得上才算填上)→ ② 同行的原生 select
    // → ③ 同行里能写的真空件 → ④ 报手选。
    for (const j of pending) {
      const val = profile[j.key]
      if (val === null || val === undefined || val === '') {
        rep.manual.push(`${j.label}(只读弹层,点开手选:无答案)`); continue
      }
      if (await pickInto(j.el, val, rep.debug, j.label)) {
        j.el.classList.add('af-filled')
        rep.clicked.push(`${j.label} → ${val}`)
        continue
      }
      const sel = siblingSelect(j.el, val)
      if (sel) {
        j.el.classList.add('af-filled')
        rep.verify.push(`${j.label}(${val})· 弹层没点开,选的是同行那个原生 select`)
        continue
      }
      const sib = writableSibling(j.el)
      if (sib && String(sib.value || '').trim()) {
        rep.kept.push(`${j.label}(同行真控件里已有「${sib.value}」)`)
        continue
      }
      if (sib) {
        setNative(sib, String(val))
        sib.classList.add('af-filled')
        rep.verify.push(`${j.label}(${val})· 弹层没点到,写的是同行${visible(sib) ? '另一个' : '隐藏的'}真控件,显示框不会变`)
        continue
      }
      rep.manual.push(`${j.label}(只读弹层,点开手选:${val})`)
    }

    // B 路线:标签撞不到别名(通常是控件被拆成两个、显示框抢了标签),但这一行里有个
    // **能写的真空 input** —— 往它写值。护栏:只写 text/tel/number/search(不含 hidden,
    // 框架的隐藏域存的是 id/token,覆盖成简历文本会静默污染提交体);一行里这类控件
    // 超过 3 个说明已经爬到子表里,整行放弃;已有值的不动;一律进 `👀` 不进 `✅`。
    for (const el of probeOnly) {
      // 和 matchField 同一套规矩:**任一**候选标签撞上黑名单就整字段放弃。
      // 不能"跳过被拉黑的那个、用下一个",那正是学校名填进验证码框的成因
      let raw = null, blocked = false
      for (const s of labelCandidates(el)) {
        const q = (s || '').trim()
        if (!q) continue
        if (isBlocked(q)) { blocked = true; break }
        const t = norm(q)
        if (!t || t.length > 14) continue
        if (KEYS.some(x => t.includes(norm(x)))) { raw = q; break }
      }
      if (blocked || !raw) continue
      const t = norm(raw)
      if (used.has(t)) continue
      const k = KEYS.find(x => t.includes(norm(x)))
      if (!k) continue
      const sib = writableSibling(el)
      if (!sib) continue
      used.add(t)
      if (ALIAS[k] === '@cascader') { rep.cascader.push(raw); continue }
      const val = profile[ALIAS[k]]
      if (val === null || val === undefined || val === '') { rep.missing.push(raw); continue }
      if (String(sib.value || '').trim()) { rep.kept.push(`${raw}(已有「${sib.value}」)`); continue }
      setNative(sib, String(val))
      sib.classList.add('af-filled')
      rep.verify.push(`${raw}(${val})· 写的是${visible(el) ? '同排的空' : '隐藏'}真控件,显示框不会变,提交前核实`)
    }

    // 纯 div 假控件的行上面两轮都遍历不到(它整行没有一个 input),只能靠合成点击
    const done = new Set()
    for (const row of document.querySelectorAll(ROW_SEL)) {
      const tn = rowTitle(row)
      if (!tn || row.querySelector('input, select, textarea')) continue
      const lab = tn.textContent.trim()
      const t = norm(lab)
      if (!t || t.length > 14 || isBlocked(t) || used.has(t) || done.has(t)) continue
      done.add(t)
      const k = KEYS.find(x => t.includes(norm(x)))
      if (!k) continue                       // 认不出说法的留给 🚫 那栏报出来
      used.add(t)
      if (ALIAS[k] === '@cascader') { rep.cascader.push(lab); continue }
      const val = profile[ALIAS[k]]
      if (val === null || val === undefined || val === '') { rep.missing.push(lab); continue }
      if (divRowChoose(row, String(val))) { rep.clicked.push(`${lab} → ${val}`); continue }
      // 选项不在 DOM 里(要点开才渲染的 div 假下拉):按同一套快照差分试着点开它。
      // 护栏没变——只点"因为这次点击才出现、而且文案正好等于答案"的叶子,不猜、不硬点容器
      const ctr = row.querySelector('[class*="select"], [class*="picker"], [class*="cascader"], [role="combobox"]')
      if (ctr && await openChoose(ctr, String(val), rep.debug, lab)) {
        rep.clicked.push(`${lab} → ${val}(点开 div 假下拉选的)`)
        continue
      }
      rep.skipped.push(`${lab}(没找到文案等于「${val}」的选项,一个节点都没点)`)
    }
    rep.unknown = orphanLabels(used, profile)
    return rep
  }

  // 页面上写着标签、扩展却没碰到任何控件的字段。北森有相当一部分控件是 div 假的
  // (自定义单选、假下拉),querySelectorAll('input') 根本看不见它们。
  // 与其静默漏掉让人以为"没填就是没这个字段",不如列出来。
  const LABEL_SEL = 'label, [class*="label"], [class*="title"], th, dt'
  function orphanLabels(used, profile) {
    const out = []
    const seen = new Set()
    for (const n of document.querySelectorAll(LABEL_SEL)) {
      if (!visible(n) || n.querySelector('input, select, textarea')) continue
      const raw = (n.textContent || '').trim()
      const t = norm(raw)
      if (!t || t.length > 14 || isBlocked(t) || used.has(t) || seen.has(t)) continue
      const k = KEYS.find(x => t.includes(norm(x)))
      if (k) {                       // 别名表里有,但控件没命中 —— 多半是假控件
        seen.add(t)
        out.push(`${raw}(假控件,填不了:${profile[ALIAS[k]] || '无答案'})`)
      } else if (hasControlNearby(n)) {
        // 不在别名表。要求它的容器里真的有个控件,否则「教育经历」这类分区标题
        // 也会带 class*="title" 混进来,清单就废了。
        // 剩下的基本都是**子表的列**(开始时间/结束时间/语言类型/掌握程度/听说):
        // 一个标签在页面上出现好几行,对应哪一段经历只有人知道,故意不加别名。
        seen.add(t)
        out.push(`${raw}(没有对应答案,手填)`)
      }
    }
    return out.slice(0, 20)
  }

  function hasControlNearby(n) {
    // 只认"行级"容器:里面有一到三个控件。「教育经历」这类分区标题往上数是整个表单,
    // 控件几十上百个,不该被当成字段标签
    for (let i = 0, p = n && n.parentElement; i < 3 && p; i++, p = p.parentElement) {
      const cnt = p.querySelectorAll('input:not([type=hidden]), select, textarea').length
      if (cnt >= 1 && cnt <= 3) return true
    }
    return false
  }

  function render(rep, err) {
    let box = document.getElementById('af-report')
    if (!box) {
      box = document.createElement('div')
      box.id = 'af-report'
      document.body.appendChild(box)
    }
    const line = (t, arr) => arr.length ? `<div class="af-g"><b>${t} ${arr.length}</b>${
      arr.map(x => `<span>${x}</span>`).join('')}</div>` : ''
    const hand = rep.missing.length + rep.cascader.length + rep.manual.length + rep.unknown.length
    // 诊断栏不是给人处理的,是给开发者看的:它记的是"这个字段的弹层我点了没开、
    // 开成的样子是什么、里面有哪些文案"。真实页上一次跑就能定死下一版怎么改,
    // 不用再靠猜(上一版猜 class 名,8 个字段全哑)。
    const dbg = (rep.debug || []).map(x => String(x).slice(0, 160)).slice(0, 14)
    box.innerHTML = err
      ? `<div class="af-h bad">填充失败</div><div class="af-g"><span>${err}</span></div>`
      : `<div class="af-h">已填 ${rep.filled.length} · 保留 ${rep.kept.length} · 待你补 ${hand}</div>`
        + line('✅', rep.filled)
        + line('🎯 替你点开选中(假控件)', rep.clicked)
        + line('👀 下拉/日期类:提交前核实组件认没认', rep.verify)
        + line('✋ 省市区手选', rep.cascader)
        + line('🔒 只读弹层,点开自己选', rep.manual)
        + line('⚠️ 答案表里是空的', rep.missing)
        + line('↷ 页面已有值', rep.kept)
        + line('❓ 没匹配上', rep.skipped)
        + line('🚫 扩展够不着的字段', rep.unknown)
        + line('🔍 诊断(截图发我,不用管)', dbg)
        + `<div class="af-f">检查高亮字段后<b>自己点提交</b>——本扩展不会替你提交。`
          + (rep.clicked.length
            ? `本次替你点了 ${rep.clicked.length} 处:只点弹层里的选项,级联另外点了弹层<b>内部</b>的「确定」;`
              + '提交/下一步一次都没点。</div>'
            : '没点过任何控件以外的东西。</div>')
    box.style.display = 'block'
  }

  async function run() {
    const resp = await chrome.runtime.sendMessage({ type: 'getProfile' })
    if (!resp || !resp.ok) { render(null, (resp && resp.error) || '拿不到后端数据') ; return }
    if (resp.profile._missing) { render(null, resp.profile._missing); return }
    render(await fillAll(resp.profile))
  }

  const btn = document.createElement('button')
  btn.id = 'af-btn'
  btn.textContent = '自动填充'
  btn.title = '从本机 127.0.0.1:8000/api/profile 取答案,只填不交'
  btn.addEventListener('click', run)
  ;(document.body || document.documentElement).appendChild(btn)

  // 给自动化测试和只读探针留的钩子,页面脚本用不到
  window.__autofill = { fillAll, matchField, render, labelCandidates, visible, norm }
})()
