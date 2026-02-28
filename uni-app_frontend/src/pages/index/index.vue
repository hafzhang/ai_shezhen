<template>
  <div class="container">
    <div class="header">
      <h1 class="title">AI舌诊智能诊断</h1>
      <p class="subtitle">基于人工智能的中医舌诊分析</p>
    </div>

    <div class="content">
      <!-- User info section -->
      <div class="user-card" v-if="userStore.isLoggedIn && userStore.userInfo">
        <div class="user-info">
          <img
            class="avatar"
            :src="userStore.userInfo.avatar_url || '/static/default-avatar.png'"
            alt="Avatar"
          />
          <div class="user-details">
            <div class="nickname">{{ userStore.userInfo.nickname || '用户' }}</div>
            <div class="phone">{{ maskPhone(userStore.userInfo.phone) }}</div>
          </div>
        </div>
        <div class="user-actions">
          <a class="action-link" @click="goToProfile">个人中心</a>
        </div>
      </div>

      <!-- Welcome card -->
      <div class="welcome-card">
        <div class="logo">🏥</div>
        <h2 class="welcome-text">欢迎使用AI舌诊系统</h2>
        <p class="description">通过拍照上传舌部照片，AI将为您分析舌象特征并给出健康建议</p>
      </div>

      <!-- Start diagnosis button -->
      <div class="action-buttons">
        <button class="btn btn-primary" @click="startDiagnosis">
          开始诊断
        </button>
      </div>

      <!-- Feature grid -->
      <div class="feature-grid">
        <div class="feature-item" @click="viewHistory">
          <div class="feature-icon">📋</div>
          <div class="feature-title">历史记录</div>
          <div class="feature-desc">查看诊断历史</div>
        </div>

        <div class="feature-item" @click="viewHealthRecords">
          <div class="feature-icon">📊</div>
          <div class="feature-title">健康档案</div>
          <div class="feature-desc">管理健康数据</div>
        </div>

        <div class="feature-item" @click="viewStatistics">
          <div class="feature-icon">📈</div>
          <div class="feature-title">健康趋势</div>
          <div class="feature-desc">查看健康变化</div>
        </div>

        <div class="feature-item" @click="goToSettings">
          <div class="feature-icon">⚙️</div>
          <div class="feature-title">设置</div>
          <div class="feature-desc">应用设置</div>
        </div>
      </div>

      <!-- Login prompt for non-logged-in users -->
      <div class="info-section" v-if="!userStore.isLoggedIn">
        <p class="info-text">登录后可保存诊断记录并查看历史</p>
        <div class="info-actions">
          <button class="btn btn-text" @click="goToLogin">登录</button>
          <span class="divider">|</span>
          <button class="btn btn-text" @click="goToRegister">注册</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'

const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  console.log('Index page mounted')
  console.log('Is logged in:', userStore.isLoggedIn)

  // Fetch user info if logged in
  if (userStore.isLoggedIn && !userStore.userInfo) {
    userStore.fetchUserInfo()
  }
})

function maskPhone(phone: string): string {
  if (!phone) return ''
  return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
}

function startDiagnosis() {
  router.push('/diagnosis')
}

function viewHistory() {
  if (!userStore.isLoggedIn) {
    alert('请先登录')
    goToLogin()
    return
  }
  router.push('/history')
}

function viewHealthRecords() {
  if (!userStore.isLoggedIn) {
    alert('请先登录')
    goToLogin()
    return
  }
  router.push('/health-records')
}

function viewStatistics() {
  if (!userStore.isLoggedIn) {
    alert('请先登录')
    goToLogin()
    return
  }
  // Statistics page - to be implemented
  alert('健康趋势功能即将上线')
}

function goToSettings() {
  router.push('/settings')
}

function goToProfile() {
  router.push('/profile')
}

function goToLogin() {
  router.push('/login')
}

function goToRegister() {
  router.push('/register')
}
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.header {
  padding: 40px 30px 20px;
  text-align: center;
}

.title {
  font-size: 28px;
  font-weight: bold;
  color: #ffffff;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin: 0;
}

.content {
  flex: 1;
  padding: 20px 20px 40px;
}

.user-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.avatar {
  width: 50px;
  height: 50px;
  border-radius: 25px;
  background: #f0f0f0;
  object-fit: cover;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nickname {
  font-size: 16px;
  font-weight: 500;
  color: #333333;
}

.phone {
  font-size: 13px;
  color: #999999;
}

.user-actions {
  display: flex;
  align-items: center;
}

.action-link {
  font-size: 14px;
  color: #667eea;
  cursor: pointer;
  text-decoration: none;
}

.welcome-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 30px 20px;
  text-align: center;
  margin-bottom: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.logo {
  font-size: 60px;
  margin-bottom: 15px;
}

.welcome-text {
  font-size: 20px;
  font-weight: bold;
  color: #333333;
  margin: 0 0 10px 0;
}

.description {
  font-size: 14px;
  color: #666666;
  line-height: 1.6;
  padding: 0 10px;
  margin: 0;
}

.action-buttons {
  margin-bottom: 20px;
}

.btn {
  width: 100%;
  height: 50px;
  border-radius: 25px;
  font-size: 18px;
  font-weight: 500;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-text {
  background: transparent;
  color: #667eea;
  font-size: 15px;
  height: auto;
  padding: 0;
  display: inline;
  border: none;
  cursor: pointer;
}

.btn-text:hover {
  opacity: 0.7;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

.feature-item {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 20px 15px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: transform 0.2s;
  cursor: pointer;
}

.feature-item:hover {
  transform: scale(0.98);
}

.feature-icon {
  font-size: 36px;
  margin-bottom: 10px;
}

.feature-title {
  font-size: 14px;
  font-weight: 500;
  color: #333333;
  margin-bottom: 5px;
}

.feature-desc {
  font-size: 12px;
  color: #999999;
}

.info-section {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  backdrop-filter: blur(10px);
}

.info-text {
  font-size: 14px;
  color: #ffffff;
  margin: 0 0 15px 0;
}

.info-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 15px;
}

.divider {
  color: rgba(255, 255, 255, 0.6);
}

.info-actions .btn-text {
  color: #ffffff;
  font-size: 15px;
}

/* Dark mode styles */
:global(.dark-mode) .container {
  background: linear-gradient(135deg, #4a5a9a 0%, #5a4a7a 100%);
}

:global(.dark-mode) .user-card,
:global(.dark-mode) .welcome-card,
:global(.dark-mode) .feature-item {
  background: rgba(42, 42, 42, 0.95);
}

:global(.dark-mode) .nickname,
:global(.dark-mode) .welcome-text,
:global(.dark-mode) .feature-title {
  color: #e0e0e0;
}

:global(.dark-mode) .phone,
:global(.dark-mode) .description,
:global(.dark-mode) .feature-desc {
  color: #aaaaaa;
}

:global(.dark-mode) .action-link {
  color: #8b9cf5;
}

:global(.dark-mode) .info-section {
  background: rgba(0, 0, 0, 0.2);
}
</style>
