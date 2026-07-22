import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/images', name: 'Images', component: () => import('@/views/Images.vue') },
  { path: '/database', name: 'Database', component: () => import('@/views/Database.vue') },
  { path: '/classify', name: 'Classify', component: () => import('@/views/Classify.vue') },
  { path: '/similar', name: 'Similar', component: () => import('@/views/Similar.vue') },
  { path: '/identify', name: 'Identify', component: () => import('@/views/Identify.vue') },
  { path: '/auto', name: 'Auto', component: () => import('@/views/Auto.vue') },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
