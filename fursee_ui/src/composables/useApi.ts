import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.request.use(
  (config) => {
    let fp = localStorage.getItem('fursee_fp')
    if (!fp) {
      fp = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2, 18)
      localStorage.setItem('fursee_fp', fp)
    }
    config.headers.set('X-Fingerprint', fp)
    const t = localStorage.getItem('fursee_admin_token')
    if (t) config.headers.set('X-Admin-Token', t)
    return config
  },
  (err) => Promise.reject(err)
)

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.error || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export function useApi() {
  async function uploadImages(category: string, files: File[], onProgress?: (pct: number) => void) {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    const { data } = await api.post(`/images/${category}/upload`, form, {
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  }

  async function startPipeline(type: string, params: Record<string, any>) {
    const { data } = await api.post(`/pipeline/${type}`, params)
    return data as { task_id: string }
  }

  async function getAutoHistory() {
    const { data } = await api.get('/results/auto')
    return data as { fingerprint: string; runs: any[]; count: number }
  }

  async function verifyAdmin() {
    const { data } = await api.get('/admin/verify')
    return data as { admin: boolean; reason?: string }
  }

  async function getQuota() {
    const { data } = await api.get('/quota')
    return data as {
      ip: string
      upload_remaining: number
      upload_max: number
      upload_ok: boolean
      task_remaining: number
      task_max: number
      task_ok: boolean
      next_reset_in: number
    }
  }

  function setAdminToken(token: string) {
    if (token) localStorage.setItem('fursee_admin_token', token)
    else localStorage.removeItem('fursee_admin_token')
  }

  function getAdminToken() {
    return localStorage.getItem('fursee_admin_token') || ''
  }

  return {
    uploadImages,
    startPipeline,
    getAutoHistory,
    verifyAdmin,
    getQuota,
    setAdminToken,
    getAdminToken,
  }
}
