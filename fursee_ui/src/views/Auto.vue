<template>
  <div class="auto-page">

    <!-- Append mode indicator -->
    <n-card v-if="appendTargetId && !running" class="mb-12" size="small" :bordered="false" style="background:#fff7e6">
      <div style="display:flex;align-items:center;gap:8px;font-size:13px">
        <span>{{ t('auto.append_to', { id: appendTargetId }) }}</span>
        <n-button size="tiny" @click="appendTargetId = ''">{{ t('auto.cancel') }}</n-button>
      </div>
    </n-card>

    <n-card :title="appendTargetId ? t('auto.new_title') : t('auto.title')" class="mb-12" v-if="!running && !currentRunId">
      <div class="step-desc">{{ appendTargetId ? t('auto.append_desc') : t('auto.desc') }}</div>

      <div
        class="dropzone"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
        :class="{ 'dropzone-active': dragOver }"
        @click="fileInput?.click()"
      >
        <input ref="fileInput" type="file" multiple accept="image/*" style="display:none" @change="onFileChange" />
        <div class="upload-area" v-if="!uploading">
          <p class="upload-title">{{ $t('auto.upload_title') }}</p>
          <p class="upload-hint">{{ $t('images.format_hint') }}</p>
        </div>
        <div class="upload-area" v-else>
          <n-progress type="line" :percentage="uploadPct" indicator-placement="inside" style="max-width:300px;margin:0 auto" />
          <p class="upload-hint" style="margin-top:4px">{{ uploadStatus || uploadPct + '%' }}</p>
        </div>
      </div>

      <div v-if="uploadCount" class="upload-summary">
        {{ $t('auto.uploaded', { n: uploadCount }) }}
      </div>

      <div v-if="uploadCount || appendTargetId" class="action-bar">
        <n-button type="primary" size="large" @click="startAuto" block style="height:44px;font-size:16px">
          {{ appendTargetId ? t('auto.append_run') : t('auto.start') }}
        </n-button>
        <n-collapse style="margin-top:8px">
          <n-collapse-item :title="$t('auto.params_title')" name="p">
            <div class="param-row">
              <div class="param-item"><label class="param-label">{{ $t('database.confidence') }}</label><n-slider v-model:value="conf" :min="0.1" :max="0.9" :step="0.05" /><span class="slider-val">{{ conf.toFixed(2) }}</span></div>
              <div class="param-item"><label class="param-label">{{ $t('database.iou') }}</label><n-slider v-model:value="iou" :min="0.1" :max="0.9" :step="0.05" /><span class="slider-val">{{ iou.toFixed(2) }}</span></div>
            </div>
            <div class="param-row">
              <div class="param-item"><label class="param-label">{{ $t('classify.eps_start') }}</label><n-input-number v-model:value="epsStart" :min="0.5" :max="3" :step="0.1" style="width:100%" /></div>
              <div class="param-item"><label class="param-label">{{ $t('classify.eps_stop') }}</label><n-input-number v-model:value="epsStop" :min="0.5" :max="3" :step="0.1" style="width:100%" /></div>
              <div class="param-item"><label class="param-label">{{ $t('classify.eps_step') }}</label><n-input-number v-model:value="epsStep" :min="0.01" :max="0.5" :step="0.01" style="width:100%" /></div>
            </div>
          </n-collapse-item>
        </n-collapse>
      </div>
    </n-card>

    <n-card v-if="running" :title="`${t('auto.progress')} ${currentStage}`" class="mb-12">
      <n-progress v-if="progress.total" type="line" :percentage="progressPct" indicator-placement="inside" style="margin-bottom:12px" />
      <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log }}</div>
    </n-card>

    <template v-if="currentRun">
      <n-card class="mb-12 current-run" size="small">
        <template #header>
          <div class="current-run-header">
            <span>{{ t('auto.current_run') }} · {{ currentRun.run_id }} · {{ currentRun.total }}{{ t('auto.images') }}</span>
            <n-button size="tiny" @click="resetCurrent">{{ t('auto.new_upload') }}</n-button>
          </div>
        </template>
        <div class="result-toolbar">
          <n-button type="primary" @click="downloadZip(currentRun.run_id)" :loading="zipping" size="small"><Package :size="14" style="display:inline" /> {{ t('auto.download_zip') }}</n-button>
        </div>
        <div v-for="entry in currentRun.entries" :key="entry.name" style="margin-top:10px">
          <div class="result-title">{{ entry.name }}</div>
          <div class="result-grid">
            <div v-for="img in entry.images" :key="img" class="result-img-wrap">
              <img :src="`/api/results/auto/run/${currentRun.run_id}/image/${entry.name}/${encodeURIComponent(img)}?thumb=1`" :alt="img" class="result-img" />
              <div class="result-label">{{ img }}</div>
            </div>
          </div>
        </div>
      </n-card>
    </template>

    <n-card :title="t('auto.history')" class="mb-12">
      <template v-if="historyRuns.length">
        <n-collapse>
          <n-collapse-item v-for="run in historyRuns" :key="run.run_id" :title="`${run.run_id} · ${run.total} ${t('auto.images')}`" :name="run.run_id">
            <div class="result-toolbar" style="margin-bottom:8px">
              <n-button size="tiny" @click="downloadZip(run.run_id)" :loading="zipping"><Package :size="14" style="display:inline" /> {{ t('auto.download_zip') }}</n-button>
              <n-button v-if="!running" size="tiny" @click="setAppend(run.run_id)">+ {{ t('auto.append_images') }}</n-button>
              <n-button size="tiny" @click="deleteRun(run.run_id)" :loading="deleting === run.run_id"><Trash2 :size="14" style="display:inline" /></n-button>
            </div>
            <div v-for="entry in run.entries" :key="entry.name" style="margin-top:8px">
              <div class="result-title">{{ entry.name }}</div>
              <div class="result-grid">
                <div v-for="img in entry.images" :key="img" class="result-img-wrap">
                  <img :src="`/api/results/auto/run/${run.run_id}/image/${entry.name}/${encodeURIComponent(img)}?thumb=1`" :alt="img" class="result-img" />
                  <div class="result-label">{{ img }}</div>
                </div>
              </div>
            </div>
          </n-collapse-item>
        </n-collapse>
      </template>
      <n-empty v-else :description="t('auto.no_history')" style="margin:20px 0" />
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

import { Upload, Package, Trash2 } from '@lucide/vue'
import { useI18n } from 'vue-i18n'
import {
  NCard, NButton, NProgress, NCollapse, NCollapseItem, NEmpty,
  NSlider, NInputNumber, useMessage,
} from 'naive-ui'
import { useApi } from '@/composables/useApi'
import { useWs, type ProgressEvent } from '@/composables/useWs'

const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const { connect } = useWs()

const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)
const uploading = ref(false)
const uploadPct = ref(0)
const uploadStatus = ref('')
const uploadCount = ref(0)

const conf = ref(0.5)
const iou = ref(0.45)
const epsStart = ref(1.0)
const epsStop = ref(2.0)
const epsStep = ref(0.01)

const running = ref(false)
const currentStage = ref('')
const logs = ref<string[]>([])
const progress = ref({ current: 0, total: 0 })
const zipping = ref(false)
const deleting = ref('')

const currentRunId = ref('')
interface AutoEntry {
  name: string
  images: string[]
}

interface AutoRun {
  run_id: string
  total: number
  entries: AutoEntry[]
}

const currentRun = ref<AutoRun | null>(null)
const historyRuns = ref<AutoRun[]>([])

const progressPct = computed(() => progress.value.total ? Math.round((progress.value.current / progress.value.total) * 100) : 0)

const appendTargetId = ref('')

function setAppend(runId: string) {
  appendTargetId.value = runId
  currentRunId.value = ''
  currentRun.value = null
  logs.value = []
  progress.value = { current: 0, total: 0 }
}

async function doUpload(files: FileList | File[]) {
  const arr = Array.from(files).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f.name))
  if (!arr.length) return
  uploading.value = true; uploadPct.value = 0; uploadStatus.value = '上传中...'
  let done = 0
  const total = arr.length
  try {
    for (const file of arr) {
      await api.uploadImages('auto_uploads', [file], (p) => { uploadPct.value = Math.round((done + p / 100) / total * 100) })
      done++
      uploadPct.value = Math.round(done / total * 100)
    }
    uploadCount.value += arr.length
  } catch (e: any) { msg.error(e.message) }
  finally { uploading.value = false; uploadPct.value = 0; uploadStatus.value = '' }
}
function onDrop(e: DragEvent) { dragOver.value = false; if (e.dataTransfer?.files) doUpload(e.dataTransfer.files) }
function onFileChange(e: Event) { const t = e.target as HTMLInputElement; if (t.files) doUpload(t.files); t.value = '' }

async function startAuto() {
  if (!uploadCount.value && !appendTargetId.value) return
  running.value = true; logs.value = []; progress.value = { current: 0, total: 0 }
  currentRunId.value = ''; currentRun.value = null
  currentStage.value = '🔍 ' + t('auto.step_detect')
  try {
    const params: Record<string, number | boolean | string> = {
      conf: conf.value, iou: iou.value,
      eps_start: epsStart.value, eps_stop: epsStop.value, eps_step: epsStep.value,
      use_augmentation: true, augmentation_count: 4,
    }
    if (appendTargetId.value) params.existing_run_id = appendTargetId.value
    const res = await api.startPipeline('auto', params)
    connect(res.task_id, handleProgress)
  } catch (e: any) { msg.error(e.message); running.value = false }
}

function handleProgress(e: ProgressEvent) {
  if (e.event === 'progress') {
    progress.value = { current: e.current ?? 0, total: e.total ?? 0 }
    if (e.stage?.includes('Step 1')) currentStage.value = '🔍 ' + t('auto.step_detect')
    else if (e.stage?.includes('Step 2')) currentStage.value = '🧠 ' + t('auto.step_feature')
    else if (e.stage?.includes('Step 3')) currentStage.value = '🔗 ' + t('auto.step_cluster')
    logs.value.push(`${e.stage}: ${e.current}/${e.total}`)
  } else if (e.event === 'log') {
    logs.value.push(e.message ?? '')
  } else if (e.event === 'complete') {
    currentStage.value = '✅ ' + t('auto.step_done')
    progress.value = { current: 1, total: 1 }
    logs.value.push('✅ ' + t('auto.complete'))
    msg.success(t('auto.complete'))
    running.value = false
    appendTargetId.value = ''
    refreshAfterRun()
  } else if (e.event === 'error') {
    logs.value.push('❌ ' + (e.message ?? ''))
    msg.error(e.message ?? 'error'); running.value = false
  }
}

async function refreshAfterRun() {
  await loadHistory()
  if (historyRuns.value.length) {
    currentRun.value = historyRuns.value[historyRuns.value.length - 1]
    currentRunId.value = currentRun.value.run_id
  }
}

async function loadHistory() {
  try {
    const data = await api.getAutoHistory()
    historyRuns.value = data.runs || []
  } catch { console.warn('loadHistory failed') }
}

async function deleteRun(runId: string) {
  deleting.value = runId
  try {
    await api.deleteRun(runId)
    loadHistory()
  } catch { msg.error('删除失败') }
  finally { deleting.value = '' }
}

async function downloadZip(runId: string) {
  zipping.value = true
  try {
    const a = document.createElement('a')
    a.href = `/api/results/auto/run/${runId}/zip`
    a.download = `auto_${runId}.zip`
    a.click()
  } catch (e: any) { msg.error(e.message) }
  finally { zipping.value = false }
}

function resetCurrent() {
  currentRunId.value = ''
  currentRun.value = null
  uploadCount.value = 0
  logs.value = []
  progress.value = { current: 0, total: 0 }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.auto-page { max-width: 900px; margin:0 auto; }
.mb-12 { margin-bottom:12px; }
.step-desc { font-size:13px; color:#666; margin-bottom:16px; line-height:1.6; }
.dropzone { border:2px dashed #d9d9d9; border-radius:8px; cursor:pointer; transition:all .2s; }
.dropzone:hover, .dropzone-active { border-color:#333; background:#f8f8f8; }
.upload-area { padding:32px; text-align:center; }
.upload-title { margin:4px 0; font-size:15px; color:#333; font-weight:500; }
.upload-hint { margin:4px 0; font-size:12px; color:#999; }
.upload-summary { margin:12px 0; font-size:13px; color:#666; }
.action-bar { margin-top:16px; }
.param-row { display:flex; gap:12px; margin-bottom:8px; }
.param-item { flex:1; min-width:0; }
.param-label { display:block; font-size:12px; color:#666; margin-bottom:4px; }
.slider-val { margin-left:8px; color:#666; font-size:12px; }
.log-line { font-size:12px; color:#666; padding:2px 0; font-family:monospace; }
.current-run-header { display:flex; justify-content:space-between; align-items:center; width:100%; }
.result-toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.result-title { font-weight:600; font-size:13px; margin-bottom:4px; color:#333; }
.result-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(100px,1fr)); gap:6px; }
.result-img-wrap { border:1px solid #eee; border-radius:6px; overflow:hidden; background:#fff; }
.result-img { width:100%; height:100px; object-fit:cover; display:block; }
.result-label { padding:2px 4px; font-size:10px; color:#666; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.current-run { border:1px solid #333 !important; }
@media (max-width:768px) {
  .param-row { flex-direction:column; gap:0; }
  .result-grid { grid-template-columns:repeat(3,1fr); }
  .upload-area { padding:20px; }
}
</style>
