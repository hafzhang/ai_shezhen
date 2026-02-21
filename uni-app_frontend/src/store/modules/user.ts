import { defineStore } from 'pinia'
import { ref } from 'vue'
import { request, getToken, setTokens, clearTokens, getUserInfo, setUserInfo as saveUserInfo, isUniApp } from '@/utils/request'

interface UserInfo {
  id: string
  phone?: string
  nickname?: string
  avatar_url?: string
  openid?: string
  openid_type?: string
  email?: string
  created_at?: string
}

export const useUserStore = defineStore('user', () => {
  // Initialize token from storage
  const token = ref(getToken())

  // Initialize userInfo from storage (H5 auto-login)
  const storedUserInfo = getUserInfo()
  const userInfo = ref<UserInfo | null>(storedUserInfo)

  const isLoggedIn = ref(!!token.value && !!userInfo.value)

  function setUserInfo(info: UserInfo) {
    userInfo.value = info
    // Persist to localStorage for H5
    saveUserInfo(info)
  }

  function setAccessToken(accessToken: string, refreshToken: string) {
    setTokens(accessToken, refreshToken)
    token.value = accessToken
    isLoggedIn.value = true
  }

  function logout() {
    clearTokens()
    token.value = ''
    userInfo.value = null
    isLoggedIn.value = false
    // User info is cleared in clearTokens()
  }

  /**
   * Initialize authentication state from storage
   * Call this on app startup to restore user session
   */
  async function initializeAuth() {
    const storedToken = getToken()
    const storedUserInfo = getUserInfo()

    if (storedToken && storedUserInfo) {
      token.value = storedToken
      userInfo.value = storedUserInfo
      isLoggedIn.value = true

      // Verify token is still valid by fetching fresh user info
      try {
        await fetchUserInfo()
      } catch (error) {
        // Token might be expired, clear storage
        console.log('Token expired, clearing storage')
        logout()
      }
    }
  }

  async function fetchUserInfo() {
    if (!token.value) {
      return
    }

    try {
      const response = await request<UserInfo>({
        url: '/users/me',
        method: 'GET'
      })

      if (response.success) {
        setUserInfo(response.data)
      }
    } catch (error) {
      console.error('Failed to fetch user info:', error)
    }
  }

  async function login(phone: string, password: string) {
    try {
      const response = await request<{
        access: string
        refresh: string
        user: UserInfo
      }>({
        url: '/auth/login',
        method: 'POST',
        data: { phone, password }
      })

      if (response.success && response.data) {
        setAccessToken(response.data.access, response.data.refresh)
        setUserInfo(response.data.user)
        return true
      }

      return false
    } catch (error: any) {
      console.error('Login failed:', error)
      // Re-throw with more user-friendly message
      if (error?.message) {
        throw error
      }
      throw new Error('登录失败，请稍后重试')
    }
  }

  async function register(phone: string, password: string, nickname: string) {
    try {
      const response = await request<{
        access: string
        refresh: string
        user: UserInfo
      }>({
        url: '/auth/register',
        method: 'POST',
        data: { phone, password, nickname }
      })

      if (response.success && response.data) {
        setAccessToken(response.data.access, response.data.refresh)
        setUserInfo(response.data.user)
        return true
      }

      return false
    } catch (error) {
      console.error('Register failed:', error)
      throw error
    }
  }

  /**
   * WeChat mini-program login
   * Call wx.login() to get code, then exchange for JWT tokens
   */
  async function wechatLogin(nickname?: string, avatarUrl?: string) {
    if (!isUniApp) {
      throw new Error('WeChat login is only available in mini-program environment')
    }

    try {
      // Call wx.login() to get code
      const loginRes = await uni.login({
        provider: 'weixin'
      })

      if (!loginRes.code) {
        throw new Error('获取微信登录凭证失败')
      }

      // Send code to backend
      const response = await request<{
        access_token: string
        refresh_token: string
        user: UserInfo
      }>({
        url: '/auth/wechat',
        method: 'POST',
        data: {
          code: loginRes.code,
          nickname,
          avatar_url: avatarUrl
        }
      })

      if (response.success && response.data) {
        setAccessToken(response.data.access_token, response.data.refresh_token)
        setUserInfo(response.data.user)
        return true
      }

      return false
    } catch (error: any) {
      console.error('WeChat login failed:', error)
      if (error?.message) {
        throw error
      }
      throw new Error('微信登录失败，请稍后重试')
    }
  }

  /**
   * Douyin mini-program login
   * Call tt.login() to get code, then exchange for JWT tokens
   */
  async function douyinLogin(nickname?: string, avatarUrl?: string) {
    if (!isUniApp) {
      throw new Error('Douyin login is only available in mini-program environment')
    }

    try {
      // Call tt.login() to get code
      const loginRes = await uni.login({
        provider: 'douyin'
      })

      if (!loginRes.code) {
        throw new Error('获取抖音登录凭证失败')
      }

      // Send code to backend
      const response = await request<{
        access_token: string
        refresh_token: string
        user: UserInfo
      }>({
        url: '/auth/douyin',
        method: 'POST',
        data: {
          code: loginRes.code,
          nickname,
          avatar_url: avatarUrl
        }
      })

      if (response.success && response.data) {
        setAccessToken(response.data.access_token, response.data.refresh_token)
        setUserInfo(response.data.user)
        return true
      }

      return false
    } catch (error: any) {
      console.error('Douyin login failed:', error)
      if (error?.message) {
        throw error
      }
      throw new Error('抖音登录失败，请稍后重试')
    }
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    setUserInfo,
    setAccessToken,
    logout,
    initializeAuth,
    fetchUserInfo,
    login,
    register,
    wechatLogin,
    douyinLogin
  }
}, {
  persist: true
})

// Export UserInfo type for use in other modules
export type { UserInfo }
