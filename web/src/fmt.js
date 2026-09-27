// 状态与分数的展示口径集中在这里,和 src/ledger.py 的状态机保持一致。

export const STATUSES = ['待投', '暂缓', '已投', '笔试', '面试', 'offer', '挂', '跳过', '未入台账']

export const STATUS_TONE = {
  待投: 'blue', 暂缓: 'gray', 已投: 'violet', 笔试: 'amber',
  面试: 'cyan', offer: 'green', 挂: 'red', 跳过: 'dim', 未入台账: 'dim',
}

// 投递进度链,用于时间线排序和"走到哪一步了"
export const FLOW = ['待投', '已投', '笔试', '面试', 'offer']

export const ADVICE_TONE = { 投: 'green', 观望: 'amber', 不投: 'red' }

export function tone(status) {
  return STATUS_TONE[status] || 'dim'
}

export function starsStyle(score) {
  return { '--p': Math.max(0, Math.min(100, score || 0)) + '%' }
}

export function tier(score) {
  if (score >= 85) return '第一档'
  if (score >= 82) return '第二档'
  if (score >= 78) return '第三档'
  if (score >= 70) return '第四档'
  return '偏低'
}

export function shortTime(ts) {
  return (ts || '').slice(5, 16)
}
