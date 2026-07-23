<template>
  <div class="similar-page">
    <div class="top-row">
      <n-card :title="$t('similar.title')" class="flex-1">
        <div class="dropzone" @dragover.prevent="dragOver=true" @dragleave="dragOver=false" @drop.prevent="onDrop" :class="{'dropzone-active':dragOver}" @click="fileInput?.click()">
          <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileChange" />
          <div class="upload-area" v-if="!uploading"><p class="upload-title">{{ $t('similar.drag_hint') }}</p><p class="upload-hint">{{ $t('similar.hint_detail') }}</p></div>
          <div class="upload-area" v-else><n-progress type="line" :percentage="uploadPct" indicator-placement="inside" style="max-width:200px;margin:0 auto" /></div>
        </div>
        <img v-if="refImage" :src="refImageUrl + '?thumb=1'" class="ref-preview" />
      </n-card>
      <n-card :title="$t('similar.settings')" class="settings-card">
        <n-form label-placement="top"><n-form-item :label="$t('similar.topk')"><n-input-number v-model:value="k" :min="1" :max="100" style="width:100%" /></n-form-item><n-form-item><n-button type="primary" @click="startSearch" :loading="running" :disabled="running||!refImage" block>{{ $t('similar.search') }}</n-button></n-form-item></n-form>
      </n-card>
    </div>
    <n-card v-if="running||logs.length" :title="$t('similar.progress')" class="mb-12"><div v-for="(log,i) in logs" :key="i" class="log-line">{{ log }}</div></n-card>
    <n-card v-if="results.length" :title="$t('similar.results')"><div v-for="entry in results" :key="entry.name" style="margin-bottom:14px"><div class="result-title">{{ entry.name }}</div><div v-if="entry.type==='folder'" class="result-grid"><div v-for="img in entry.images" :key="img" class="result-img-wrap"><img :src="api.getResultImageUrl('similar',`${entry.name}/${img}`,true)" :alt="img" class="result-img" /><div class="result-label">{{ img }}</div></div></div></div></n-card>
  </div>
</template>
<script setup lang="ts">
import { ref,onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCard,NProgress,NForm,NFormItem,NInputNumber,NButton,useMessage } from 'naive-ui'
import { useApi } from '@/composables/useApi'
import { useWs,type ProgressEvent } from '@/composables/useWs'
const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const { connect } = useWs()
const fileInput=ref<HTMLInputElement|null>(null);const k=ref(10);const running=ref(false);const logs=ref<string[]>([]);const results=ref<any[]>([]);const refImage=ref(false);const refImageUrl=ref('');const dragOver=ref(false);const uploading=ref(false);const uploadPct=ref(0)
async function doUpload(files:FileList|File[]){const arr=Array.from(files).filter(f=>/\.(jpg|jpeg|png|webp)$/i.test(f.name));if(!arr.length)return;uploading.value=true;uploadPct.value=0;try{await api.uploadImages('sim_targets',arr,(p)=>uploadPct.value=p);refImage.value=true;loadRefImage()}catch(e:any){msg.error(e.message)}finally{uploading.value=false}}
function onDrop(e:DragEvent){dragOver.value=false;if(e.dataTransfer?.files)doUpload(e.dataTransfer.files)}
function onFileChange(e:Event){const t=e.target as HTMLInputElement;if(t.files)doUpload(t.files);t.value=''}
async function loadRefImage(){try{const data=await api.listImages('sim_targets');if(data.images?.length)refImageUrl.value=`/api/images/sim_targets/image/${encodeURIComponent(data.images[data.images.length-1].name)}`}catch{}}
async function startSearch(){running.value=true;logs.value=[];results.value=[];try{const res=await api.startPipeline('similar',{k:k.value});connect(res.task_id,handleProgress)}catch(e:any){msg.error(e.message);running.value=false}}
function handleProgress(e:ProgressEvent){if(e.event==='progress'){logs.value.push(`${e.stage}: ${e.current}/${e.total}`)}else if(e.event==='log'){logs.value.push(e.message??'')}else if(e.event==='complete'){logs.value.push(`✅ ${t('similar.complete')}`);msg.success(t('similar.complete'));running.value=false;loadResults()}else if(e.event==='error'){logs.value.push(`❌ ${e.message}`);msg.error(e.message??t('similar.failed'));running.value=false}}
async function loadResults(){try{const data=await api.listResults('similar');results.value=data.entries||[]}catch{}}
onMounted(loadRefImage)
</script>
<style scoped>
.similar-page{max-width:900px;margin:0 auto}.top-row{display:flex;gap:12px;margin-bottom:12px}.flex-1{flex:1;min-width:0}.settings-card{width:240px;flex-shrink:0}.dropzone{border:2px dashed #d9d9d9;border-radius:6px;cursor:pointer;transition:all .2s}.dropzone:hover,.dropzone-active{border-color:#333;background:#f8f8f8}.upload-area{padding:20px;text-align:center}.upload-title{margin:4px 0;color:#333;font-size:14px}.upload-hint{margin:4px 0;font-size:12px;color:#999}.ref-preview{width:100%;max-height:200px;object-fit:contain;margin-top:8px;border-radius:4px}.mb-12{margin-bottom:12px}.log-line{font-size:12px;color:#666;padding:2px 0;font-family:monospace}.result-title{font-weight:600;font-size:14px;margin-bottom:6px;color:#333}.result-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px}.result-img-wrap{border:1px solid #eee;border-radius:6px;overflow:hidden;background:#fff}.result-img{width:100%;height:100px;object-fit:cover;display:block}.result-label{padding:3px 5px;font-size:10px;color:#666;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:768px){.top-row{flex-direction:column}.settings-card{width:100%}.result-grid{grid-template-columns:repeat(3,1fr)}}
</style>
