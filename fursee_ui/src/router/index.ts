import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/auto' },
  { path: '/auto', name: 'Auto', component: () => import('@/views/Auto.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
