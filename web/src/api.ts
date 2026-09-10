// API 客户端（v0.1 同源部署，FastAPI 托管；开发态走 Vite 代理）
// 服务端启用 Bearer 认证时：localStorage 的 token 自动携带；401 弹输入（部署场景）
async function request(path: string, options: RequestInit = {}, retried = false): Promise<any> {
  const token = localStorage.getItem('yz_token') || ''
  const resp = await fetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  })
  if (resp.status === 401 && !retried) {
    const input = prompt('该服务已启用访问认证，请输入访问令牌（Access Token）：')
    if (input !== null) {
      localStorage.setItem('yz_token', input.trim())
      return request(path, options, true)
    }
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export const api = {
  get: (path: string) => request(path),
  post: (path: string, body: unknown) =>
    request(path, { method: 'POST', body: JSON.stringify(body) }),
}
