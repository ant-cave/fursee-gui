import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.error || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export function useApi() {
  async function getStats() {
    const { data } = await api.get('/stats')
    return data
  }

  async function listImages(category: string) {
    const { data } = await api.get(`/images/${category}`)
    return data
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

  async function deleteImage(category: string, filename: string) {
    const { data } = await api.delete(`/images/${category}/${encodeURIComponent(filename)}`)
    return data
  }

  async function startPipeline(type: string, params: Record<string, any>) {
    const { data } = await api.post(`/pipeline/${type}`, params)
    return data as { task_id: string }
  }

  async function getTask(taskId: string) {
    const { data } = await api.get(`/pipeline/tasks/${taskId}`)
    return data
  }

  async function listTasks() {
    const { data } = await api.get('/pipeline/tasks')
    return data.tasks as any[]
  }

  async function listResults(resultType: string) {
    const { data } = await api.get(`/results/${resultType}`)
    return data
  }

  function getResultImageUrl(resultType: string, path: string, thumb = false) {
    return `/api/results/${resultType}/image/${path}${thumb ? '?thumb=1' : ''}`
  }

  return {
    getStats,
    listImages,
    uploadImages,
    deleteImage,
    startPipeline,
    getTask,
    listTasks,
    listResults,
    getResultImageUrl,
  }
}
