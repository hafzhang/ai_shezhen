import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/pages/index/index.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/login/index.vue')
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/pages/register/index.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
