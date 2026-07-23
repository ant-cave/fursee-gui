<template>
  <div class="images-page">
    <n-card style="margin-bottom:12px">
      <div class="dropzone" @dragover.prevent="dragOver=true" @dragleave="dragOver=false" @drop.prevent="onDrop" :class="{'dropzone-active':dragOver}" @click="fileInput?.click()">
        <input ref="fileInput" type="file" multiple accept="image/*" style="display:none" @change="onFileChange" />
        <div class="upload-area" v-if="!uploading">
          <p class="upload-title">{{ $t('images.drag_hint') }}</p>
          <p class="upload-hint">{{ $t('images.format_hint') }}</p>
        </div>
        <div class="upload-area" v-else>
          <n-progress type="line" :percentage="uploadPct" indicator-placement="inside" style="max-width:300px;margin:0 auto" />
          <p class="upload-hint" style="margin-top:6px">{{ uploadPct }}%</p>
        </div>
      </div>
    </n-card>
    <n-card>
      <n-tabs :value="activeTab" @update:value="switchTab" type="line" size="small">
        <n-tab name="images" :tab="`${$t('images.tab_input')} (${counts.images})`" />
        <n-tab name="sim_targets" :tab="`${$t('images.tab_sim')} (${counts.sim_targets})`" />
        <n-tab name="id_targets" :tab="`${$t('images.tab_id')} (${counts.id_targets})`" />
      </n-tabs>
      <n-empty v-if="!images.length" :description="$t('images.no_images')" style="margin-top:20px" />
      <div v-else class="image-grid">
        <div v-for="img in images" :key="img.name" class="img-card">
          <img :src="`/api/images/${activeTab}/image/${encodeURIComponent(img.name)}?thumb=1`" :alt="img.name" class="img-thumb" @error="($event.target as HTMLImageElement).style.display='none'" />
          <div class="img-name">{{ img.name }}</div>
          <n-button size="tiny" quaternary circle class="img-del" @click="deleteImg(img.name)">✕</n-button>
        </div>
      </div>
    </n-card>
  </div>
</template>
<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { NCard, NProgress, NTabs, NTab, NEmpty, NButton, useMessage } from 'naive-ui'
import { useApi } from '@/composables/useApi'
const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const activeTab = ref('images')
const images = ref<any[]>([])
const counts = reactive({ images:0, sim_targets:0, id_targets:0 })
const dragOver = ref(false)
const uploading = ref(false)
const uploadPct = ref(0)
const fileInput = ref<HTMLInputElement|null>(null)
async function loadImages() {
  try { const data = await api.listImages(activeTab.value); images.value = data.images||[]; counts[activeTab.value as keyof typeof counts] = data.count }
  catch (e: any) { msg.error(e.message) }
}
function switchTab(tab:string) { activeTab.value=tab; loadImages() }
async function deleteImg(name:string) {
  try { await api.deleteImage(activeTab.value, name); msg.success(`${t('images.deleted')}: ${name}`); loadImages() }
  catch (e: any) { msg.error(e.message) }
}
async function uploadFiles(files:FileList|File[]) {
  const arr = Array.from(files).filter(f=>/\.(jpg|jpeg|png|webp)$/i.test(f.name)); if(!arr.length) return
  uploading.value=true; uploadPct.value=0
  try { await api.uploadImages(activeTab.value, arr, (p)=>uploadPct.value=p); msg.success(`已上传 ${arr.length} 张`); loadImages() }
  catch (e: any) { msg.error(e.message) }
  finally { uploading.value=false; uploadPct.value=0 }
}
function onDrop(e:DragEvent) { dragOver.value=false; if(e.dataTransfer?.files) uploadFiles(e.dataTransfer.files) }
function onFileChange(e:Event) { const t = e.target as HTMLInputElement; if(t.files) uploadFiles(t.files); t.value='' }
async function loadAllCounts() { for(const cat of ['images','sim_targets','id_targets'] as const) { try{const data=await api.listImages(cat);counts[cat]=data.count}catch{} } }
onMounted(() => { loadImages(); loadAllCounts() })
</script>
<style scoped>
.images-page { max-width:900px; margin:0 auto; }
.dropzone { border:2px dashed #d9d9d9; border-radius:8px; cursor:pointer; transition:all .2s; }
.dropzone:hover, .dropzone-active { border-color:#333; background:#f8f8f8; }
.upload-area { padding:24px; text-align:center; }
.upload-title { margin:4px 0; font-size:14px; color:#333; }
.upload-hint { margin:4px 0; font-size:12px; color:#999; }
.image-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:10px; margin-top:12px; }
.img-card { position:relative; border:1px solid #eee; border-radius:6px; overflow:hidden; background:#fff; }
.img-thumb { width:100%; height:100px; object-fit:cover; display:block; }
.img-name { padding:4px 6px; font-size:10px; color:#666; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.img-del { position:absolute; top:3px; right:3px; color:#fff; background:rgba(0,0,0,0.4); }
@media (max-width:768px) { .image-grid { grid-template-columns:repeat(3,1fr); gap:6px; } .img-thumb { height:80px; } }
</style>
