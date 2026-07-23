import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export interface AutoRun {
  run_id: string
  total: number
  entries: { name: string; images: string[] }[]
}

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

  async function startPipeline(type: string, params: Record<string, string | number | boolean>) {
    const { data } = await api.post(`/pipeline/${type}`, params)
    return data as { task_id: string }
  }

  async function getAutoHistory() {
    const { data } = await api.get('/results/auto')
    return data as { runs: AutoRun[]; count: number }
  }

  async function deleteRun(runId: string) {
    await api.delete(`/results/auto/run/${runId}`)
  }

  return {
    uploadImages,
    startPipeline,
    getAutoHistory,
    deleteRun,
  }
}
