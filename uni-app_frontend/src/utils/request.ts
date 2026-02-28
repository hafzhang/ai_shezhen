interface RequestConfig {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: any
  header?: Record<string, string>
  timeout?: number
}

interface ApiResponse<T = any> {
  success: boolean
  message?: string
  error?: string
  data: T
}

const BASE_URL = import.meta.env.DEV ? '/api/v1' : 'https://api.shezhen.com/api/v1'

// Check if running in uni-app environment
const isUniApp = typeof uni !== 'undefined'

// Storage abstraction for uni-app and web
const storage = {
  getItem(key: string): string | null {
    if (isUniApp) {
      return uni.getStorageSync(key) || null
    }
    return localStorage.getItem(key)
  },
  setItem(key: string, value: string): void {
    if (isUniApp) {
      uni.setStorageSync(key, value)
    } else {
      localStorage.setItem(key, value)
    }
  },
  removeItem(key: string): void {
    if (isUniApp) {
      uni.removeStorageSync(key)
    } else {
      localStorage.removeItem(key)
    }
  }
}

// Navigation abstraction
function navigateToLogin() {
  if (isUniApp) {
    uni.navigateTo({
      url: '/pages/login/index'
    })
  } else {
    window.location.href = '/login'
  }
}

function getToken(): string {
  return storage.getItem('access_token') || ''
}

function getRefreshToken(): string {
  return storage.getItem('refresh_token') || ''
}

function setTokens(accessToken: string, refreshToken: string) {
  storage.setItem('access_token', accessToken)
  storage.setItem('refresh_token', refreshToken)
}

function clearTokens() {
  storage.removeItem('access_token')
  storage.removeItem('refresh_token')
  storage.removeItem('user_info')
}

// User info storage functions
function getUserInfo(): any {
  const info = storage.getItem('user_info')
  if (info) {
    try {
      return JSON.parse(info)
    } catch {
      return null
    }
  }
  return null
}

function setUserInfo(userInfo: any): void {
  storage.setItem('user_info', JSON.stringify(userInfo))
}

let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token))
  refreshSubscribers = []
}

async function refreshToken(): Promise<string> {
  const refreshTokenValue = getRefreshToken()
  if (!refreshTokenValue) {
    throw new Error('No refresh token available')
  }

  let result: ApiResponse<{ access: string; refresh: string }>

  if (isUniApp) {
    const response = await uni.request({
      url: `${BASE_URL}/auth/refresh`,
      method: 'POST',
      data: { refresh_token: refreshTokenValue },
      header: { 'Content-Type': 'application/json' }
    })
    result = response.data as ApiResponse<{ access: string; refresh: string }>
  } else {
    const response = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshTokenValue })
    })
    result = await response.json() as ApiResponse<{ access: string; refresh: string }>
  }

  if (result.success && result.data) {
    setTokens(result.data.access, result.data.refresh)
    return result.data.access
  }

  throw new Error('Token refresh failed')
}

async function request<T = any>(config: RequestConfig): Promise<ApiResponse<T>> {
  const {
    url,
    method = 'GET',
    data,
    header = {},
    timeout = 30000
  } = config

  const requestHeader = {
    'Content-Type': 'application/json',
    ...header
  }

  const token = getToken()
  if (token) {
    requestHeader['Authorization'] = `Bearer ${token}`
  }

  try {
    let response: any
    let statusCode: number
    let result: ApiResponse<T>

    if (isUniApp) {
      // Use uni.request for uni-app environment
      response = await uni.request({
        url: `${BASE_URL}${url}`,
        method,
        data,
        header: requestHeader,
        timeout
      })
      statusCode = response.statusCode
      result = response.data as ApiResponse<T>
    } else {
      // Use fetch for web environment
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), timeout)

      const fetchResponse = await fetch(`${BASE_URL}${url}`, {
        method,
        headers: requestHeader,
        body: method !== 'GET' && data ? JSON.stringify(data) : undefined,
        signal: controller.signal
      })
      clearTimeout(timeoutId)

      statusCode = fetchResponse.status
      result = await fetchResponse.json() as ApiResponse<T>
    }

    // Token expired, try to refresh
    if (statusCode === 401 && token) {
      if (!isRefreshing) {
        isRefreshing = true
        try {
          const newToken = await refreshToken()
          isRefreshing = false
          onTokenRefreshed(newToken)

          // Retry original request with new token
          return request<T>({ ...config, header: { ...header, Authorization: `Bearer ${newToken}` } })
        } catch (error) {
          isRefreshing = false
          clearTokens()
          navigateToLogin()
          throw error
        }
      } else {
        // Wait for token refresh
        return new Promise((resolve, reject) => {
          subscribeTokenRefresh(token => {
            request<T>({ ...config, header: { ...header, Authorization: `Bearer ${token}` } })
              .then(resolve)
              .catch(reject)
          })
        })
      }
    }

    if (statusCode >= 200 && statusCode < 300) {
      return result
    }

    throw new Error(result.error || result.message || 'Request failed')
  } catch (error: any) {
    if (error.name === 'AbortError' || (error.errMsg && error.errMsg.includes('timeout'))) {
      throw new Error('请求超时，请检查网络连接')
    }
    if (error.errMsg && error.errMsg.includes('fail')) {
      throw new Error('网络连接失败，请检查网络设置')
    }
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error('网络连接失败，请检查网络设置')
    }
    throw error
  }
}

// Convenience methods
const http = {
  get: <T = any>(url: string, config?: Omit<RequestConfig, 'url' | 'method'>) =>
    request<T>({ ...config, url, method: 'GET' }),

  post: <T = any>(url: string, data?: any, config?: Omit<RequestConfig, 'url' | 'method' | 'data'>) =>
    request<T>({ ...config, url, method: 'POST', data }),

  put: <T = any>(url: string, data?: any, config?: Omit<RequestConfig, 'url' | 'method' | 'data'>) =>
    request<T>({ ...config, url, method: 'PUT', data }),

  delete: <T = any>(url: string, config?: Omit<RequestConfig, 'url' | 'method'>) =>
    request<T>({ ...config, url, method: 'DELETE' })
}

export { request, http, getToken, setTokens, clearTokens, getUserInfo, setUserInfo, isUniApp }
export type { RequestConfig, ApiResponse }
