<template>
  <div class="container">
    <div class="header">
      <h1 class="title">AI舌诊智能诊断系统</h1>
      <p class="subtitle">基于人工智能的中医舌诊分析</p>
    </div>

    <div class="content">
      <div class="welcome-card">
        <div class="logo">🏥</div>
        <h2 class="welcome-text">欢迎使用AI舌诊系统</h2>
        <p class="description">通过拍照上传舌部照片，AI将为您分析舌象特征并给出健康建议</p>
      </div>

      <div class="action-buttons">
        <button class="btn btn-primary" @click="startDiagnosis">开始诊断</button>
        <button class="btn btn-secondary" @click="viewHistory">历史记录</button>
      </div>

      <div class="info-section" v-if="!isLoggedIn">
        <p class="info-text">登录后可保存诊断记录</p>
        <button class="btn btn-text" @click="goToLogin">立即登录</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLoggedIn = ref(false)

onMounted(() => {
  checkLoginStatus()
})

function checkLoginStatus() {
  const token = localStorage.getItem('access_token')
  isLoggedIn.value = !!token
}

function startDiagnosis() {
  // TODO: Navigate to diagnosis page when implemented
  console.log('Navigate to diagnosis')
}

function viewHistory() {
  if (!isLoggedIn.value) {
    alert('请先登录')
    goToLogin()
    return
  }
  // TODO: Navigate to history page when implemented
  console.log('Navigate to history')
}

function goToLogin() {
  router.push('/login')
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
  padding: 40px 30px 30px;
  text-align: center;
}

.title {
  font-size: 28px;
  font-weight: bold;
  color: #ffffff;
  margin: 0 0 10px 0;
}

.subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.8);
  margin: 0;
}

.content {
  flex: 1;
  padding: 30px;
}

.welcome-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 40px 30px;
  text-align: center;
  margin-bottom: 30px;
}

.logo {
  font-size: 80px;
  margin-bottom: 20px;
}

.welcome-text {
  font-size: 22px;
  font-weight: bold;
  color: #333333;
  margin: 0 0 15px 0;
}

.description {
  font-size: 16px;
  color: #666666;
  line-height: 1.6;
  margin: 0;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.btn {
  height: 50px;
  border-radius: 25px;
  font-size: 18px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: transform 0.2s;

  &:hover {
    transform: translateY(-2px);
  }
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
}

.btn-secondary {
  background: #f5f5f5;
  color: #333333;
}

.btn-text {
  background: transparent;
  color: #667eea;
  font-size: 16px;
  height: auto;
  padding: 0;
}

.info-section {
  text-align: center;
  margin-top: 40px;
}

.info-text {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0 0 10px 0;
}
</style>
