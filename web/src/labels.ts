// 枚举值中文显示映射（仅显示层——存储值是数据契约，不改）
export const VALUE_LABELS: Record<string, string> = {
  // 严重程度
  blocker: '致命', critical: '严重', major: '较重', minor: '较轻', trivial: '轻微',
  // 状态
  Open: '进行中', InProgress: '进行中', Closed: '已关闭', Resolved: '已解决',
  Rejected: '已驳回', Done: '已完成', Active: '启用', Inactive: '停用',
  applied: '已生效', staged: '待审批', approved: '已批准', reverted: '已撤销',
  published: '已上架', draft: '草稿',
  // 类型
  positive: '正向', negative: '反向',
}

export function vLabel(v: unknown): string {
  const s = String(v ?? '')
  return VALUE_LABELS[s] || s
}
