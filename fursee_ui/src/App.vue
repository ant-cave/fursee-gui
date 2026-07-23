<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-dialog-provider>
      <n-message-provider>
        <n-layout style="height: 100vh">
          <n-layout-header
            bordered
            style="height: 50px; display: flex; align-items: center; padding: 0 12px; background: #1a1a1a; gap: 8px"
          >
            <n-button quaternary style="color: #fff; padding: 0 6px" @click="menuOpen = !menuOpen">
              <Menu :size="20" />
            </n-button>
            <div style="font-size: 15px; font-weight: 700; color: #fff; letter-spacing: 1px">{{ $t('app.title') }}</div>
            <div style="flex: 1" />
            <n-button size="tiny" quaternary style="color: #aaa" @click="toggleLang">{{ $t('lang.switch') }}</n-button>
            <n-tag v-if="showWs" :type="wsConnected ? 'success' : 'error'" size="tiny" round>
              {{ wsConnected ? $t('status.connected') : $t('status.disconnected') }}
            </n-tag>
          </n-layout-header>

          <n-layout position="absolute" style="top: 50px; bottom: 0; left: 0; right: 0">
            <n-layout has-sider style="height: 100%">
              <n-layout-sider
                bordered
                :width="220"
                :collapsed-width="0"
                :collapsed="!menuOpen"
                :show-trigger="false"
                :native-scrollbar="false"
                style="background: #1a1a1a; transition: width 0.25s"
                content-style="display: flex; flex-direction: column; height: 100%;"
              >
                <div style="padding: 14px 16px 10px; border-bottom: 1px solid #2a2a2a">
                  <div style="font-size: 13px; color: #888">{{ $t('app.subtitle') }}</div>
                </div>
                <n-menu
                  :value="activeKey"
                  :options="menuOptions"
                  @update:value="goTo"
                  style="flex: 1; padding: 8px 0"
                  :indent="20"
                />
                <div style="padding: 10px 16px; border-top: 1px solid #2a2a2a; font-size: 11px; color: #555">
                  {{ $t('app.version') }}
                </div>
              </n-layout-sider>

              <n-layout>
                <n-layout-content
                  content-style="padding: 16px; overflow-y: auto;"
                  style="height: 100%; background: #f5f5f5"
                >
                  <router-view />
                </n-layout-content>
                <n-layout-footer bordered style="padding:6px 16px;font-size:11px;color:#999;text-align:center;background:#fafafa">
                  Fursee © Jundi Wu · GUI Shell by ant-cave · AGPL-3.0 ·
                  <a href="https://github.com/ant-cave/fursee" target="_blank" style="color:#1890ff;text-decoration:none">GitHub</a> ·
                  <a href="mailto:antmmmmm@outlook.com" style="color:#1890ff;text-decoration:none">antmmmmm@outlook.com</a>
                </n-layout-footer>
              </n-layout>
            </n-layout>
          </n-layout>
        </n-layout>
      </n-message-provider>
      <Disclaimer />
    </n-dialog-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted, h } from 'vue'
import { Menu, Star } from '@lucide/vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NConfigProvider, NDialogProvider, NMessageProvider, NLayout, NLayoutSider,
  NLayoutHeader, NLayoutContent, NMenu, NButton, NTag,
} from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { themeOverrides } from '@/styles/theme'
import { useWs } from '@/composables/useWs'
import Disclaimer from '@/views/Disclaimer.vue'

const router = useRouter()
const route = useRoute()
const { t, locale } = useI18n()
const { connected: wsConnected } = useWs()

const showWs = ref(false)
let wsTimer: ReturnType<typeof setTimeout> | null = null
watch(wsConnected, (v) => {
  if (wsTimer) clearTimeout(wsTimer)
  if (v) {
    showWs.value = true
  } else {
    wsTimer = setTimeout(() => { showWs.value = false }, 5000)
  }
})
onUnmounted(() => { if (wsTimer) clearTimeout(wsTimer) })

const menuOpen = ref(window.innerWidth > 768)

watch(() => route.path, () => {
  if (window.innerWidth <= 768) menuOpen.value = false
})

function toggleLang() {
  locale.value = locale.value === 'zh' ? 'en' : 'zh'
  localStorage.setItem('fursee_lang', locale.value)
}

const saved = localStorage.getItem('fursee_lang')
if (saved === 'en' || saved === 'zh') locale.value = saved



const activeKey = computed(() => route.path)

const menuOptions = computed(() => [
  { label: t('nav.auto'), key: '/auto', icon: () => h(Star, { size: 16 }) },
])

function goTo(key: string) {
  router.push(key)
  if (window.innerWidth <= 768) menuOpen.value = false
}
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
.n-menu .n-menu-item-content { color: #aaa !important; }
.n-menu .n-menu-item-content--selected { color: #fff !important; background: #333 !important; }
.n-menu .n-menu-item-content:hover { color: #ddd !important; background: #2a2a2a !important; }
@media (max-width: 768px) {
  body { -webkit-text-size-adjust: 100%; }
}
</style>
