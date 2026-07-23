<template>
  <div class="dashboard">
    <div class="stat-grid">
      <n-card v-for="stat in stats" :key="stat.label" size="small" hoverable>
        <n-statistic :label="stat.label" :value="stat.value">
          <template #suffix><span class="stat-unit">{{ stat.unit }}</span></template>
        </n-statistic>
      </n-card>
    </div>
    <n-card :title="$t('dashboard.quick_actions')" class="mb-16">
      <div class="flex-wrap gap-12">
        <n-button type="primary" @click="quickColdBuild" :loading="busy">{{ $t('dashboard.cold_build') }}</n-button>
        <n-button @click="handleReset">{{ $t('dashboard.reset_all') }}</n-button>
      </div>
    </n-card>
    <n-card :title="$t('dashboard.recent_tasks')">
      <n-table v-if="tasks.length" :bordered="false" size="small">
        <thead><tr><th>ID</th><th>Type</th><th>State</th><th>Error</th></tr></thead>
        <tbody>
          <tr v-for="t in tasks.slice(0,10)" :key="t.id">
            <td><code>{{ t.id }}</code></td><td>{{ t.type }}</td>
            <td><n-tag :type="stateType(t.state)" size="small">{{ t.state }}</n-tag></td>
            <td class="err-cell">{{ t.error || '-' }}</td>
          </tr>
        </tbody>
      </n-table>
      <n-empty v-else :description="$t('dashboard.no_tasks')" />
    </n-card>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NCard, NStatistic, NTable, NTag, NEmpty, useMessage } from 'naive-ui'
import { useApi } from '@/composables/useApi'
const { t } = useI18n()
const api = useApi()
const msg = useMessage()
const busy = ref(false)
const tasks = ref<any[]>([])
const stats = ref([
  { label: t('dashboard.input_images'), value: 0, unit: t('dashboard.files') },
  { label: t('dashboard.sim_targets'), value: 0, unit: t('dashboard.files') },
  { label: t('dashboard.id_targets'), value: 0, unit: t('dashboard.files') },
  { label: t('dashboard.db_vectors'), value: 0, unit: t('dashboard.vectors') },
])
async function load() {
  try {
    const data = await api.getStats()
    tasks.value = data.tasks || []
    stats.value = [
      { label: t('dashboard.input_images'), value: data.images?.count ?? 0, unit: t('dashboard.files') },
      { label: t('dashboard.sim_targets'), value: data.sim_targets?.count ?? 0, unit: t('dashboard.files') },
      { label: t('dashboard.id_targets'), value: data.id_targets?.count ?? 0, unit: t('dashboard.files') },
      { label: t('dashboard.db_vectors'), value: data.database?.vectors ?? 0, unit: t('dashboard.vectors') },
    ]
  } catch (e: any) { msg.error(e.message) }
}
async function quickColdBuild() {
  busy.value = true
  try { const res = await api.startPipeline('db', { mode: 'cold' }); msg.success(`Task started: ${res.task_id}`) }
  catch (e: any) { msg.error(e.message) }
  finally { busy.value = false }
}
async function handleReset() {
  try { await (await import('axios')).default.post('/api/pipeline/reset'); msg.success('Reset done'); load() }
  catch { /* ignore */ }
}
function stateType(s: string) { if (s === 'completed') return 'success'; if (s === 'failed') return 'error'; if (s === 'running') return 'info'; return 'default' }
onMounted(load)
</script>
<style scoped>
.dashboard { max-width:900px; margin:0 auto; }
.stat-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:12px; margin-bottom:16px; }
.mb-16 { margin-bottom:16px; }
.flex-wrap { display:flex; flex-wrap:wrap; gap:12px; }
.gap-12 { gap:12px; }
.stat-unit { font-size:12px; color:#999; margin-left:4px; }
.err-cell { color:#f5222d; font-size:12px; }
@media (max-width:768px) { .stat-grid { grid-template-columns:repeat(2,1fr); gap:8px; } }
</style>
