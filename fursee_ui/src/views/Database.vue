<template>
  <div class="db-page">
    <n-card :title="$t('database.title')" class="mb-12">
      <n-form label-placement="top">
        <n-form-item :label="$t('database.mode')"><n-radio-group v-model:value="mode"><n-radio value="cold">{{ $t('database.cold') }}</n-radio><n-radio value="append">{{ $t('database.append') }}</n-radio></n-radio-group></n-form-item>
        <div class="form-row"><n-form-item :label="$t('database.confidence')" class="flex-item"><n-slider v-model:value="conf" :min="0.1" :max="0.9" :step="0.05" /><span class="slider-val">{{ conf.toFixed(2) }}</span></n-form-item><n-form-item :label="$t('database.iou')" class="flex-item"><n-slider v-model:value="iou" :min="0.1" :max="0.9" :step="0.05" /><span class="slider-val">{{ iou.toFixed(2) }}</span></n-form-item></div>
        <div class="form-row"><n-form-item :label="$t('database.imgsz')" class="flex-item"><n-input-number v-model:value="imgsz" :min="640" :max="1920" :step="64" style="width:100%" /></n-form-item><n-form-item :label="$t('database.augment')" class="flex-item"><n-input-number v-model:value="augCount" :min="1" :max="10" style="width:100%" /></n-form-item></div>
        <n-form-item :label="$t('database.multi_gpu')"><n-switch v-model:value="multiGpu" /></n-form-item>
        <n-form-item><n-button type="primary" @click="startBuild" :loading="running" :disabled="running">{{ running ? $t('database.running') : $t('database.start') }}</n-button><n-button v-if="running" @click="cancelBuild" style="margin-left:8px">{{ $t('database.cancel') }}</n-button></n-form-item>
      </n-form>
    </n-card>
    <n-card v-if="running||logs.length" :title="$t('database.progress')" class="mb-12">
      <n-progress v-if="progress.total" type="line" :percentage="progressPct" indicator-placement="inside" style="margin-bottom:12px" />
      <div v-for="(log,i) in logs" :key="i" class="log-line">{{ log }}</div>
    </n-card>
  </div>
</template>
<script setup lang="ts">
import { ref,computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCard,NForm,NFormItem,NRadioGroup,NRadio,NSlider,NInputNumber,NSwitch,NButton,NProgress,useMessage } from 'naive-ui'
import { useApi } from '@/composables/useApi'
import { useWs,type ProgressEvent } from '@/composables/useWs'
const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const { connect,disconnect } = useWs()
const mode = ref('cold'); const conf = ref(0.5); const iou = ref(0.45); const imgsz = ref(1280); const augCount = ref(4); const multiGpu = ref(true)
const running = ref(false); const logs = ref<string[]>([]); const progress = ref({current:0,total:0})
const progressPct = computed(()=>progress.value.total?Math.round((progress.value.current/progress.value.total)*100):0)
async function startBuild() {
  running.value=true;logs.value=[];progress.value={current:0,total:0}
  try{const res=await api.startPipeline('db',{mode:mode.value,conf:conf.value,iou:iou.value,imgsz:imgsz.value,augmentation_count:augCount.value,use_multi_gpu:multiGpu.value});connect(res.task_id,handleProgress)}
  catch(e:any){msg.error(e.message);running.value=false}
}
function handleProgress(e:ProgressEvent){
  if(e.event==='progress'){progress.value={current:e.current??0,total:e.total??0};logs.value.push(`${e.stage}: ${e.current}/${e.total}`)}
  else if(e.event==='log'){logs.value.push(e.message??'')}
  else if(e.event==='complete'){logs.value.push(`✅ ${t('database.complete')}`);msg.success(t('database.complete'));running.value=false}
  else if(e.event==='error'){logs.value.push(`❌ ${e.message}`);msg.error(e.message??t('database.failed'));running.value=false}
}
function cancelBuild(){disconnect();running.value=false;logs.value.push(t('database.cancelled'))}
</script>
<style scoped>
.db-page { max-width:700px; margin:0 auto; }
.mb-12 { margin-bottom:12px; }
.form-row { display:flex; gap:12px; }
.flex-item { flex:1; min-width:0; }
.slider-val { margin-left:10px; color:#666; white-space:nowrap; font-size:13px; }
.log-line { font-size:12px; color:#666; padding:2px 0; font-family:monospace; }
@media (max-width:768px) { .form-row { flex-direction:column; gap:0; } }
</style>
