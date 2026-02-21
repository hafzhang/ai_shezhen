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

const BASE_URL = import.meta.env.DEV ? '/api' : 'https://api.shezhen.com/api/v2'

function getToken(): string {
  return uni.getStorageSync('access_token') || ''
}

function getRefreshToken(): string {
  return uni.getStorageSync('refresh_token') || ''
}

function setTokens(accessToken: string, refreshToken: string) {
  uni.setStorageSync('access_token', accessToken)
  uni.setStorageSync('refresh_token', refreshToken)
}

function clearTokens() {
  uni.removeStorageSync('access_token')
  uni.removeStorageSync('refresh_token')
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

async function refreshToken() {
  const refreshTokenValue = getRefreshToken()
  if (!refreshTokenValue) {
    throw new Error('No refresh token available')
  }

  const response = await uni.request({
    url: `${BASE_URL}/auth/refresh`,
    method: 'POST',
    data: { refresh_token: refreshTokenValue },
    header: { 'Content-Type': 'application/json' }
  })

  const result = response.data as ApiResponse<{ access: string; refresh: string }>

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
    const response = await uni.request({
      url: `${BASE_URL}${url}`,
      method,
      data,
      header: requestHeader,
      timeout
    })

    const result = response.data as ApiResponse<T>

    // Token expired, try to refresh
    if (response.statusCode === 401 && token) {
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

          // Navigate to login
          uni.navigateTo({
            url: '/pages/login/index'
          })

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

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return result
    }

    throw new Error(result.error || result.message || 'Request failed')
  } catch (error: any) {
    if (error.errMsg) {
      if (error.errMsg.includes('timeout')) {
        throw new Error('请求超时，请检查网络连接')
      }
      if (error.errMsg.includes('fail')) {
        throw new Error('网络连接失败，请检查网络设置')
      }
    }
    throw error
  }
}

export { request, getToken, setTokens, clearTokens }
export type { RequestConfig, ApiResponse }
