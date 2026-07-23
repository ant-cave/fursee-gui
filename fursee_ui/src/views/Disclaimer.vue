<template>
  <n-modal v-model:show="visible" :mask-closable="false" preset="card" style="max-width:560px" :title="disclaimerTitle" closable>
    <div class="disclaimer-body">
      <p><strong>{{ privacyTitle }}</strong></p>
      <ul>
        <li v-for="(item, i) in items" :key="i">{{ item }}</li>
      </ul>
      <p><strong>{{ licenseTitle }}</strong></p>
      <p>{{ licenseBody }}</p>
      <p class="disclaimer-footer">{{ footer }}</p>
    </div>
    <template #footer>
      <n-button type="primary" @click="accept">{{ acceptText }}</n-button>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { NModal, NButton } from 'naive-ui'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const visible = ref(false)

const disclaimerTitle = computed(() => t('disclaimer.title'))
const privacyTitle = computed(() => t('disclaimer.privacy_title'))
const items = computed(() => t('disclaimer.items') as unknown as string[])
const licenseTitle = computed(() => t('disclaimer.license_title'))
const licenseBody = computed(() => t('disclaimer.license_body'))
const footer = computed(() => t('disclaimer.footer'))
const acceptText = computed(() => t('disclaimer.accept'))

function accept() {
  visible.value = false
  localStorage.setItem('fursee_disclaimer', '1')
}

onMounted(() => {
  if (!localStorage.getItem('fursee_disclaimer')) {
    visible.value = true
  }
})
</script>

<style scoped>
.disclaimer-body { font-size: 13px; line-height: 1.7; color: #333; }
.disclaimer-body ul { padding-left: 18px; margin: 8px 0; }
.disclaimer-body li { margin-bottom: 6px; }
.disclaimer-footer { margin-top: 12px; font-size: 12px; color: #999; }
</style>
