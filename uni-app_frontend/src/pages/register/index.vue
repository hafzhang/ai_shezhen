<template>
  <div class="container">
    <div class="header">
      <button class="back-button" @click="goBack">←</button>
      <h1 class="title">注册</h1>
    </div>

    <div class="content">
      <div class="form-container">
        <!-- Error message display -->
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <div class="form-group">
          <label class="label">手机号</label>
          <input
            class="input"
            type="tel"
            v-model="phone"
            placeholder="请输入手机号"
            maxlength="11"
          />
        </div>

        <div class="form-group">
          <label class="label">密码</label>
          <input
            class="input"
            type="password"
            v-model="password"
            placeholder="请输入密码（6-20位）"
            maxlength="20"
          />
        </div>

        <div class="form-group">
          <label class="label">确认密码</label>
          <input
            class="input"
            type="password"
            v-model="confirmPassword"
            placeholder="请再次输入密码"
            maxlength="20"
          />
        </div>

        <div class="form-group">
          <label class="label">昵称</label>
          <input
            class="input"
            type="text"
            v-model="nickname"
            placeholder="请输入昵称"
            maxlength="20"
            @keyup.enter="handleRegister"
          />
        </div>

        <button class="btn btn-primary" @click="handleRegister" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>

        <div class="links">
          <span class="link" @click="goToLogin">已有账号？去登录</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import { handleLoginSuccess } from '@/utils/routeGuard'

const router = useRouter()
const userStore = useUserStore()
const phone = ref('')
const password = ref('')
const confirmPassword = ref('')
const nickname = ref('')
const loading = ref(false)
const errorMessage = ref('')

function goBack() {
  router.back()
}

function goToLogin() {
  router.push('/login')
}

async function handleRegister() {
  errorMessage.value = ''

  // Phone validation
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    errorMessage.value = '请输入正确的手机号'
    return
  }

  // Password validation
  if (password.value.length < 6 || password.value.length > 20) {
    errorMessage.value = '密码长度应为6-20位'
    return
  }

  // Confirm password validation
  if (password.value !== confirmPassword.value) {
    errorMessage.value = '两次密码输入不一致'
    return
  }

  // Nickname validation
  if (!nickname.value.trim()) {
    errorMessage.value = '请输入昵称'
    return
  }

  loading.value = true

  try {
    const success = await userStore.register(phone.value, password.value, nickname.value)

    if (success) {
      // Show success message and redirect using route guard
      alert('注册成功')

      setTimeout(() => {
        handleLoginSuccess()
      }, 500)
    } else {
      errorMessage.value = '注册失败，请稍后重试'
    }
  } catch (error: any) {
    console.error('Register error:', error)
    errorMessage.value = error?.message || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  background: #f5f5f5;
}

.header {
  position: relative;
  padding: 20px;
  background: #ffffff;
  text-align: center;
}

.back-button {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  font-size: 24px;
  color: #333333;
  cursor: pointer;
  padding: 5px 10px;
}

.title {
  font-size: 20px;
  font-weight: bold;
  color: #333333;
  margin: 0;
}

.content {
  padding: 20px;
}

.form-container {
  background: #ffffff;
  border-radius: 12px;
  padding: 30px 20px;
}

.error-message {
  background: #fff5f5;
  color: #e53e3e;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 20px;
  border: 1px solid #fed7d7;
}

.form-group {
  margin-bottom: 20px;
}

.label {
  display: block;
  font-size: 14px;
  color: #333333;
  margin-bottom: 8px;
}

.input {
  width: 100%;
  height: 44px;
  background: #f5f5f5;
  border-radius: 8px;
  padding: 0 12px;
  font-size: 16px;
  border: 1px solid transparent;

  &:focus {
    outline: none;
    border-color: #667eea;
  }
}

.btn {
  width: 100%;
  height: 48px;
  border-radius: 24px;
  font-size: 16px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: transform 0.2s;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
  }
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.links {
  margin-top: 20px;
  text-align: center;
}

.link {
  font-size: 14px;
  color: #667eea;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
}
</style>
