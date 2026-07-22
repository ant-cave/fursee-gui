<template>
  <div class="auto-page">
    <n-card :title="$t('auto.title')" class="mb-12">
      <div class="step-desc">{{ $t('auto.desc') }}</div>

      <div
        class="dropzone"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="onDrop"
        :class="{ 'dropzone-active': dragOver }"
        @click="fileInput?.click()"
        v-if="!running && !results.length"
      >
        <input ref="fileInput" type="file" multiple accept="image/*" style="display:none" @change="onFileChange" />
        <div class="upload-area" v-if="!uploading">
          <p class="upload-title">{{ $t('auto.upload_title') }}</p>
          <p class="upload-hint">{{ $t('images.format_hint') }}</p>
        </div>
        <div class="upload-area" v-else>
          <n-progress type="line" :percentage="uploadPct" indicator-placement="inside" style="max-width:300px;margin:0 auto" />
          <p class="upload-hint" style="margin-top:4px">{{ uploadPct }}%</p>
        </div>
      </div>

      <div v-if="uploadCount && !running && !results.length" class="upload-summary">
        {{ $t('auto.uploaded', { n: uploadCount }) }}
      </div>

      <div v-if="!running && !results.length" class="action-bar">
        <n-button type="primary" size="large" @click="startAuto" :disabled="!uploadCount" block style="height:44px;font-size:16px">
          🚀 {{ $t('auto.start') }}
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

    <n-card v-if="running" :title="`${$t('auto.progress')} ${currentStage}`" class="mb-12">
      <n-progress v-if="progress.total" type="line" :percentage="progressPct" indicator-placement="inside" style="margin-bottom:12px" />
      <div v-for="(log, i) in logs" :key="i" class="log-line">{{ log }}</div>
    </n-card>

    <template v-if="results.length">
      <n-card :title="$t('auto.results')" class="mb-12">
        <div class="result-toolbar">
          <n-button type="primary" @click="downloadZip" :loading="zipping" size="large">📦 {{ $t('auto.download_zip') }}</n-button>
          <n-button @click="resetAll">重新开始</n-button>
          <span class="result-summary">{{ totalClassified }} 张图片 · {{ results.length }} 个分类</span>
        </div>
        <n-alert type="info" closable style="margin-bottom:14px;font-size:13px">
          分类结果存储在服务器 <code style="background:#eee;padding:1px 4px;border-radius:3px">output/auto/classify/</code>，每个分类一个文件夹。点击上方按钮打包下载。
        </n-alert>
      </n-card>

      <n-card v-for="entry in results" :key="entry.name" :title="`${entry.name} (${entry.image_count} 张)`" style="margin-bottom:12px">
        <div class="result-grid">
          <div v-for="img in entry.images" :key="img" class="result-img-wrap">
            <img :src="`/api/results/auto/image/${entry.name}/${encodeURIComponent(img)}`" :alt="img" class="result-img" />
            <div class="result-label">{{ img }}</div>
          </div>
        </div>
      </n-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  NCard, NButton, NProgress, NCollapse, NCollapseItem, NAlert,
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
const results = ref<any[]>([])
const zipping = ref(false)

const progressPct = computed(() => progress.value.total ? Math.round((progress.value.current / progress.value.total) * 100) : 0)
const totalClassified = computed(() => results.value.reduce((s: number, e: any) => s + (e.image_count || 0), 0))

async function doUpload(files: FileList | File[]) {
  const arr = Array.from(files).filter(f => /\.(jpg|jpeg|png|webp)$/i.test(f.name))
  if (!arr.length) return
  uploading.value = true; uploadPct.value = 0
  try {
    await api.uploadImages('auto_uploads', arr, (p) => { uploadPct.value = p })
    uploadCount.value += arr.length
  } catch (e: any) { msg.error(e.message) }
  finally { uploading.value = false; uploadPct.value = 0 }
}
function onDrop(e: DragEvent) { dragOver.value = false; if (e.dataTransfer?.files) doUpload(e.dataTransfer.files) }
function onFileChange(e: Event) { const t = e.target as HTMLInputElement; if (t.files) doUpload(t.files); t.value = '' }

async function startAuto() {
  if (!uploadCount.value) return
  running.value = true; logs.value = []; progress.value = { current: 0, total: 0 }; results.value = []
  currentStage.value = '📷 检测中'
  try {
    const res = await api.startPipeline('auto', {
      conf: conf.value, iou: iou.value,
      eps_start: epsStart.value, eps_stop: epsStop.value, eps_step: epsStep.value,
      use_augmentation: true, augmentation_count: 4,
    })
    connect(res.task_id, handleProgress)
  } catch (e: any) { msg.error(e.message); running.value = false }
}

function handleProgress(e: ProgressEvent) {
  if (e.event === 'progress') {
    progress.value = { current: e.current ?? 0, total: e.total ?? 0 }
    if (e.stage?.includes('Step 1')) currentStage.value = '📷 检测中'
    else if (e.stage?.includes('Step 2')) currentStage.value = '🧠 提取特征中'
    else if (e.stage?.includes('Step 3')) currentStage.value = '🔗 聚类中'
    logs.value.push(`${e.stage}: ${e.current}/${e.total}`)
  } else if (e.event === 'log') {
    logs.value.push(e.message ?? '')
  } else if (e.event === 'complete') {
    currentStage.value = '✅ 完成'
    progress.value = { current: 1, total: 1 }
    logs.value.push('✅ 全流程完成！')
    msg.success('全流程完成！')
    running.value = false
    loadResults()
  } else if (e.event === 'error') {
    logs.value.push(`❌ ${e.message}`)
    msg.error(e.message ?? '失败'); running.value = false
  }
}

async function loadResults() {
  try {
    const data = await (await fetch('/api/results/auto')).json()
    results.value = data.entries || []
  } catch { /* ignore */ }
}

async function downloadZip() {
  zipping.value = true
  try {
    const a = document.createElement('a')
    a.href = '/api/results/auto/zip'
    a.download = 'auto_classify.zip'
    a.click()
  } catch (e: any) { msg.error(e.message) }
  finally { zipping.value = false }
}

function resetAll() {
  uploadCount.value = 0; logs.value = []; results.value = []
  progress.value = { current: 0, total: 0 }; running.value = false
}
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
.result-toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
.result-summary { font-size:13px; color:#999; }
.result-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(110px,1fr)); gap:8px; }
.result-img-wrap { border:1px solid #eee; border-radius:6px; overflow:hidden; background:#fff; }
.result-img { width:100%; height:110px; object-fit:cover; display:block; }
.result-label { padding:3px 5px; font-size:10px; color:#666; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
@media (max-width:768px) {
  .param-row { flex-direction:column; gap:0; }
  .result-grid { grid-template-columns:repeat(3,1fr); }
  .upload-area { padding:20px; }
}
</style>