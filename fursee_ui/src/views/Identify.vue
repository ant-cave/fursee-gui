<template>
  <div class="identify-page">
    <div class="top-row">
      <n-card :title="$t('identify.title')" class="flex-1">
        <div class="dropzone" @dragover.prevent="dragOver=true" @dragleave="dragOver=false" @drop.prevent="onDrop" :class="{'dropzone-active':dragOver}" @click="fileInput?.click()">
          <input ref="fileInput" type="file" multiple accept="image/*" style="display:none" @change="onFileChange" />
          <div class="upload-area" v-if="!uploading"><p class="upload-title">{{ $t('identify.drag_hint') }}</p><p class="upload-hint">{{ $t('identify.hint_detail') }}</p></div>
          <div class="upload-area" v-else><n-progress type="line" :percentage="uploadPct" indicator-placement="inside" style="max-width:200px;margin:0 auto" /></div>
        </div>
        <div v-if="refImages.length" class="ref-thumbs"><img v-for="img in refImages" :key="img" :src="img" class="ref-thumb" /></div>
      </n-card>
      <n-card :title="$t('identify.settings')" class="settings-card">
        <n-form label-placement="top"><n-form-item :label="$t('identify.eps_start')"><n-input-number v-model:value="epsStart" :min="0.5" :max="3" :step="0.1" style="width:100%" /></n-form-item><n-form-item :label="$t('identify.eps_stop')"><n-input-number v-model:value="epsStop" :min="0.5" :max="3" :step="0.1" style="width:100%" /></n-form-item><n-form-item><n-button type="primary" @click="startIdentify" :loading="running" :disabled="running||!hasRef" block>{{ $t('identify.start') }}</n-button></n-form-item></n-form>
      </n-card>
    </div>
    <n-card v-if="running||logs.length" :title="$t('identify.progress')" class="mb-12"><div v-for="(log,i) in logs" :key="i" class="log-line">{{ log }}</div></n-card>
    <n-card v-if="results.length" :title="$t('identify.results')"><div v-for="entry in results" :key="entry.name" style="margin-bottom:16px"><div class="result-title">{{ entry.name }} <n-tag size="small" style="margin-left:6px">{{ entry.image_count }} {{ $t('identify.images') }}</n-tag></div><div v-if="entry.type==='folder'" class="result-grid"><div v-for="img in entry.images" :key="img" class="result-img-wrap"><img :src="api.getResultImageUrl('identify',`${entry.name}/${img}`)" :alt="img" class="result-img" /><div class="result-label">{{ img }}</div></div></div></div><n-empty v-if="!results.length" :description="$t('identify.no_match')" /></n-card>
  </div>
</template>
<script setup lang="ts">
import { ref,computed,onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCard,NProgress,NForm,NFormItem,NInputNumber,NButton,NTag,NEmpty,useMessage } from 'naive-ui'
import { useApi } from '@/composables/useApi'
import { useWs,type ProgressEvent } from '@/composables/useWs'
const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const { connect } = useWs()
const fileInput=ref<HTMLInputElement|null>(null);const epsStart=ref(1.0);const epsStop=ref(2.0);const running=ref(false);const logs=ref<string[]>([]);const results=ref<any[]>([]);const refImages=ref<string[]>([]);const dragOver=ref(false);const uploading=ref(false);const uploadPct=ref(0)
const hasRef=computed(()=>refImages.value.length>0)
async function doUpload(files:FileList|File[]){const arr=Array.from(files).filter(f=>/\.(jpg|jpeg|png|webp)$/i.test(f.name));if(!arr.length)return;uploading.value=true;uploadPct.value=0;try{await api.uploadImages('id_targets',arr,(p)=>uploadPct.value=p);loadRefImages()}catch(e:any){msg.error(e.message)}finally{uploading.value=false}}
function onDrop(e:DragEvent){dragOver.value=false;if(e.dataTransfer?.files)doUpload(e.dataTransfer.files)}
function onFileChange(e:Event){const t=e.target as HTMLInputElement;if(t.files)doUpload(t.files);t.value=''}
async function loadRefImages(){try{const data=await api.listImages('id_targets');refImages.value=(data.images||[]).map((i:any)=>`/api/images/id_targets/image/${encodeURIComponent(i.name)}`)}catch{}}
async function startIdentify(){running.value=true;logs.value=[];results.value=[];try{const res=await api.startPipeline('identify',{eps_start:epsStart.value,eps_stop:epsStop.value});connect(res.task_id,handleProgress)}catch(e:any){msg.error(e.message);running.value=false}}
function handleProgress(e:ProgressEvent){if(e.event==='progress'){logs.value.push(`${e.stage}: ${e.current}/${e.total}`)}else if(e.event==='log'){logs.value.push(e.message??'')}else if(e.event==='complete'){logs.value.push(`✅ ${t('identify.complete')}`);msg.success(t('identify.complete'));running.value=false;loadResults()}else if(e.event==='error'){logs.value.push(`❌ ${e.message}`);msg.error(e.message??t('identify.failed'));running.value=false}}
async function loadResults(){try{const data=await api.listResults('identify');results.value=data.entries||[]}catch{}}
onMounted(loadRefImages)
</script>
<style scoped>
.identify-page{max-width:900px;margin:0 auto}.top-row{display:flex;gap:12px;margin-bottom:12px}.flex-1{flex:1;min-width:0}.settings-card{width:240px;flex-shrink:0}.dropzone{border:2px dashed #d9d9d9;border-radius:6px;cursor:pointer;transition:all .2s}.dropzone:hover,.dropzone-active{border-color:#333;background:#f8f8f8}.upload-area{padding:20px;text-align:center}.upload-title{margin:4px 0;color:#333;font-size:14px}.upload-hint{margin:4px 0;font-size:12px;color:#999}.ref-thumbs{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}.ref-thumb{width:64px;height:64px;object-fit:cover;border-radius:4px;border:1px solid #eee}.mb-12{margin-bottom:12px}.log-line{font-size:12px;color:#666;padding:2px 0;font-family:monospace}.result-title{font-weight:600;font-size:14px;margin-bottom:6px;color:#333}.result-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}.result-img-wrap{border:1px solid #eee;border-radius:6px;overflow:hidden;background:#fff}.result-img{width:100%;height:100px;object-fit:cover;display:block}.result-label{padding:3px 5px;font-size:10px;color:#666;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:768px){.top-row{flex-direction:column}.settings-card{width:100%}.result-grid{grid-template-columns:repeat(3,1fr)}}
</style>
