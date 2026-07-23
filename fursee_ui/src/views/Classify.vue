<template>
  <div class="classify-page">
    <n-card :title="$t('classify.title')" class="mb-12">
      <n-form label-placement="top">
        <div class="form-row"><n-form-item :label="$t('classify.eps_start')" class="flex-item"><n-input-number v-model:value="epsStart" :min="0.5" :max="3" :step="0.1" style="width:100%" /></n-form-item><n-form-item :label="$t('classify.eps_stop')" class="flex-item"><n-input-number v-model:value="epsStop" :min="0.5" :max="3" :step="0.1" style="width:100%" /></n-form-item><n-form-item :label="$t('classify.eps_step')" class="flex-item"><n-input-number v-model:value="epsStep" :min="0.01" :max="0.5" :step="0.01" style="width:100%" /></n-form-item></div>
        <n-form-item :label="$t('classify.use_aug')"><n-switch v-model:value="useAug" /></n-form-item>
        <n-form-item><n-button type="primary" @click="startClassify" :loading="running">{{ $t('classify.cluster') }}</n-button></n-form-item>
      </n-form>
    </n-card>
    <n-card v-if="running||logs.length" :title="$t('classify.progress')" class="mb-12">
      <n-progress v-if="progress.total" type="line" :percentage="progressPct" indicator-placement="inside" style="margin-bottom:12px" />
      <div v-for="(log,i) in logs" :key="i" class="log-line">{{ log }}</div>
    </n-card>
    <n-card v-if="results.length" :title="$t('classify.results')">
      <div v-for="entry in results" :key="entry.name" style="margin-bottom:14px"><div class="result-title">{{ entry.name }}</div><div v-if="entry.type==='folder'" class="result-grid"><div v-for="img in entry.images" :key="img" class="result-img-wrap"><img :src="api.getResultImageUrl('classify',`${entry.name}/${img}`)" :alt="img" class="result-img" /></div></div><div v-else class="result-size">{{ entry.size }} {{ $t('result.bytes') }}</div></div>
    </n-card>
  </div>
</template>
<script setup lang="ts">
import { ref,computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCard,NForm,NFormItem,NInputNumber,NSwitch,NButton,NProgress,useMessage } from 'naive-ui'
import { useApi } from '@/composables/useApi'
import { useWs,type ProgressEvent } from '@/composables/useWs'
const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const { connect } = useWs()
const epsStart=ref(1.0);const epsStop=ref(2.0);const epsStep=ref(0.01);const useAug=ref(true)
const running=ref(false);const logs=ref<string[]>([]);const progress=ref({current:0,total:0});const results=ref<any[]>([])
const progressPct=computed(()=>progress.value.total?Math.round((progress.value.current/progress.value.total)*100):0)
async function startClassify(){
  running.value=true;logs.value=[];progress.value={current:0,total:0};results.value=[]
  try{const res=await api.startPipeline('classify',{eps_start:epsStart.value,eps_stop:epsStop.value,eps_step:epsStep.value,use_augmentation:useAug.value});connect(res.task_id,handleProgress)}
  catch(e:any){msg.error(e.message);running.value=false}
}
function handleProgress(e:ProgressEvent){
  if(e.event==='progress'){progress.value={current:e.current??0,total:e.total??0};logs.value.push(`${e.stage}: ${e.current}/${e.total}`)}
  else if(e.event==='log'){logs.value.push(e.message??'')}
  else if(e.event==='complete'){logs.value.push(`✅ ${t('classify.complete')}`);msg.success(t('classify.complete'));running.value=false;loadResults()}
  else if(e.event==='error'){logs.value.push(`❌ ${e.message}`);msg.error(e.message??t('classify.failed'));running.value=false}
}
async function loadResults(){try{const data=await api.listResults('classify');results.value=data.entries||[]}catch{}}
</script>
<style scoped>
.classify-page{max-width:700px;margin:0 auto}.mb-12{margin-bottom:12px}.form-row{display:flex;gap:12px}.flex-item{flex:1;min-width:0}.log-line{font-size:12px;color:#666;padding:2px 0;font-family:monospace}.result-title{font-weight:600;font-size:14px;margin-bottom:6px;color:#333}.result-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:6px}.result-img-wrap{border:1px solid #eee;border-radius:4px;overflow:hidden}.result-img{width:100%;height:90px;object-fit:cover;display:block}.result-size{font-size:12px;color:#999}
@media(max-width:768px){.form-row{flex-direction:column;gap:0}.result-grid{grid-template-columns:repeat(3,1fr)}}
</style>
