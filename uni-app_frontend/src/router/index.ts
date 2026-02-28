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
  },
  {
    path: '/diagnosis',
    name: 'Diagnosis',
    component: () => import('@/pages/diagnosis/index.vue')
  },
  {
    path: '/result',
    name: 'Result',
    component: () => import('@/pages/result/index.vue')
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/pages/history/index.vue')
  },
  {
    path: '/detail/:id',
    name: 'Detail',
    component: () => import('@/pages/detail/index.vue')
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/pages/profile/index.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/pages/settings/index.vue')
  },
  {
    path: '/privacy',
    name: 'Privacy',
    component: () => import('@/pages/privacy/index.vue')
  },
  {
    path: '/terms',
    name: 'Terms',
    component: () => import('@/pages/terms/index.vue')
  },
  {
    path: '/health-records',
    name: 'HealthRecords',
    component: () => import('@/pages/health-records/index.vue')
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
