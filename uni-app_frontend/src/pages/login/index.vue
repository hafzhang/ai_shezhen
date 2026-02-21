<template>
  <div class="container">
    <div class="header">
      <button class="back-button" @click="goBack">←</button>
      <h1 class="title">登录</h1>
    </div>

    <div class="content">
      <div class="form-container">
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
            placeholder="请输入密码"
            maxlength="20"
          />
        </div>

        <button class="btn btn-primary" @click="handleLogin" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <div class="links">
          <span class="link" @click="goToRegister">还没有账号？去注册</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const phone = ref('')
const password = ref('')
const loading = ref(false)

function goBack() {
  router.back()
}

function goToRegister() {
  router.push('/register')
}

async function handleLogin() {
  // Phone validation
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    alert('请输入正确的手机号')
    return
  }

  // Password validation
  if (password.value.length < 6) {
    alert('密码至少6位')
    return
  }

  loading.value = true

  try {
    // TODO: Integrate with backend API
    // const response = await login({ phone: phone.value, password: password.value })

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000))

    alert('登录成功')

    setTimeout(() => {
      router.push('/')
    }, 500)
  } catch (error) {
    alert('登录失败，请重试')
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
