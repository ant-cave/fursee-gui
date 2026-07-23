import axios from 'axios'

let _adminToken = ''

function getOrCreateFp(): string {
  let fp = localStorage.getItem('fursee_fp')
  if (!fp) {
    fp = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2, 18)
    localStorage.setItem('fursee_fp', fp)
  }
  document.cookie = `fursee_fp=${fp}; path=/; max-age=86400; SameSite=Lax`
  return fp
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,
})

api.interceptors.request.use(
  (config) => {
    config.headers.set('X-Fingerprint', getOrCreateFp())
    if (_adminToken) config.headers.set('X-Admin-Token', _adminToken)
    return config
  },
  (err) => Promise.reject(err)
)

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 403) {
      localStorage.removeItem('fursee_fp')
      window.location.reload()
    }
    const msg = err.response?.data?.error || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export interface Quota {
  ip: string
  upload_remaining: number
  upload_max: number
  upload_ok: boolean
  upload_reset_in: number
  task_remaining: number
  task_max: number
  task_ok: boolean
  task_reset_in: number
}

export interface AutoRun {
  run_id: string
  total: number
  entries: { name: string; images: string[] }[]
}

export function useApi() {
  function _authHeaders() {
    return _adminToken ? { 'X-Admin-Token': _adminToken } as Record<string, string> : {}
  }

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

  async function startPipeline(type: string, params: Record<string, string | number | boolean>) {
    const { data } = await api.post(`/pipeline/${type}`, params)
    return data as { task_id: string }
  }

  async function getAutoHistory() {
    const { data } = await api.get('/results/auto')
    return data as { fingerprint: string; runs: AutoRun[]; count: number }
  }

  async function verifyAdmin() {
    const { data } = await api.get('/admin/verify')
    return data as { admin: boolean; reason?: string }
  }

  async function getQuota() {
    const { data } = await api.get('/quota')
    return data as Quota
  }

  function setAdminToken(token: string) {
    _adminToken = token
    if (!token) _adminToken = ''
  }

  function getAdminToken() {
    return _adminToken
  }

  async function deleteRun(runId: string) {
    await api.delete(`/results/auto/run/${runId}`)
  }

  async function getAdminQueue() {
    const { data } = await api.get('/admin/queue')
    return data as { active_fps: { ip: string; fp: string; upload_remaining: number; upload_max: number; task_remaining: number; task_max: number; ip_blocked: boolean }[] }
  }

  return {
    uploadImages,
    startPipeline,
    getAutoHistory,
    verifyAdmin,
    getQuota,
    setAdminToken,
    getAdminToken,
    deleteRun,
    getAdminQueue,
  }
}
