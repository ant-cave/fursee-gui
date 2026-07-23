import { ref } from 'vue'
import FingerprintJS from '@fingerprintjs/fingerprintjs'

const fpPromise = FingerprintJS.load()
const fingerprint = ref('')
let initialized = false

export function useFingerprint() {
  async function init() {
    if (initialized) return fingerprint.value
    initialized = true
    try {
      const agent = await fpPromise
      const result = await agent.get()
      fingerprint.value = result.visitorId
      localStorage.setItem('fursee_fp', fingerprint.value)
    } catch {
      const cached = localStorage.getItem('fursee_fp')
      fingerprint.value = cached || 'unknown'
    }
    return fingerprint.value
  }

  return { fingerprint, init }
}
