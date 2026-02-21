/**
 * Route Guard Utility for uni-app
 *
 * Provides navigation guards that check authentication before allowing access to protected pages.
 *
 * Pages that require authentication:
 * - /pages/history/index - Diagnosis history
 * - /pages/detail/index - Diagnosis details
 * - /pages/health-records/index - Health records
 *
 * Pages that don't require authentication (public):
 * - /pages/index/index - Home
 * - /pages/login/index - Login
 * - /pages/register/index - Register
 * - /pages/diagnosis/index - Diagnosis (supports anonymous)
 * - /pages/result/index - Result (supports anonymous)
 * - /pages/profile/index - Profile (shows guest view)
 * - /pages/settings/index - Settings (public)
 * - /pages/privacy/index - Privacy policy
 * - /pages/terms/index - User agreement
 */

import { useUserStore } from '@/store'
import type { UserInfo } from '@/store/modules/user'

// Pages that require authentication
const PROTECTED_PAGES = new Set([
  '/pages/history/index',
  '/pages/detail/index',
  '/pages/health-records/index'
])

// Login page path
const LOGIN_PAGE = '/pages/login/index'

// Storage key for redirect URL
const REDIRECT_KEY = '__redirect_after_login'

/**
 * Check if the current page requires authentication
 */
function requiresAuth(path: string): boolean {
  // Remove query parameters and hash
  const cleanPath = path.split('?')[0].split('#')[0]
  return PROTECTED_PAGES.has(cleanPath)
}

/**
 * Store the intended destination for redirect after login
 */
function storeRedirect(url: string): void {
  try {
    const isH5 = typeof window !== 'undefined' && typeof localStorage !== 'undefined'
    if (isH5) {
      localStorage.setItem(REDIRECT_KEY, url)
    } else {
      uni.setStorageSync(REDIRECT_KEY, url)
    }
  } catch (error) {
    console.warn('Failed to store redirect:', error)
  }
}

/**
 * Get and clear the stored redirect URL
 */
export function getStoredRedirect(): string | null {
  try {
    const isH5 = typeof window !== 'undefined' && typeof localStorage !== 'undefined'
    const redirect = isH5
      ? localStorage.getItem(REDIRECT_KEY)
      : uni.getStorageSync(REDIRECT_KEY)

    // Clear the stored redirect
    if (isH5) {
      localStorage.removeItem(REDIRECT_KEY)
    } else {
      uni.removeStorageSync(REDIRECT_KEY)
    }

    return redirect || null
  } catch (error) {
    console.warn('Failed to get stored redirect:', error)
    return null
  }
}

/**
 * Check if user is authenticated
 */
function isAuthenticated(): boolean {
  try {
    const userStore = useUserStore()
    return !!userStore.isLoggedIn && !!userStore.userInfo
  } catch (error) {
    console.warn('Failed to check authentication:', error)
    return false
  }
}

/**
 * Navigate to login page with redirect
 */
function navigateToLogin(redirectUrl?: string): void {
  if (redirectUrl) {
    storeRedirect(redirectUrl)
  }
  uni.navigateTo({
    url: LOGIN_PAGE,
    fail: () => {
      // If navigateTo fails (e.g., login page is already in stack), use reLaunch
      uni.reLaunch({
        url: LOGIN_PAGE
      })
    }
  })
}

/**
 * Show login prompt toast and navigate to login
 */
function promptLogin(redirectUrl?: string): void {
  uni.showToast({
    title: '请先登录',
    icon: 'none',
    duration: 1500
  })

  setTimeout(() => {
    navigateToLogin(redirectUrl)
  }, 1500)
}

/**
 * Wrapped navigateTo with auth check
 */
export function navigateTo(options: UniApp.NavigateToOptions): void {
  const url = options.url || ''

  if (requiresAuth(url) && !isAuthenticated()) {
    promptLogin(url)
    return
  }

  uni.navigateTo({
    ...options,
    fail: (err) => {
      console.warn('navigateTo failed:', err)
      options.fail?.(err as any)
    }
  })
}

/**
 * Wrapped redirectTo with auth check
 */
export function redirectTo(options: UniApp.RedirectToOptions): void {
  const url = options.url || ''

  if (requiresAuth(url) && !isAuthenticated()) {
    promptLogin(url)
    return
  }

  uni.redirectTo({
    ...options,
    fail: (err) => {
      console.warn('redirectTo failed:', err)
      options.fail?.(err as any)
    }
  })
}

/**
 * Wrapped reLaunch with auth check
 */
export function reLaunch(options: UniApp.ReLaunchOptions): void {
  const url = options.url || ''

  if (requiresAuth(url) && !isAuthenticated()) {
    promptLogin(url)
    return
  }

  uni.reLaunch({
    ...options,
    fail: (err) => {
      console.warn('reLaunch failed:', err)
      options.fail?.(err as any)
    }
  })
}

/**
 * Wrapped switchTab with auth check
 * Note: switchTab cannot navigate to login page directly (only tabBar pages)
 * For protected tabBar pages, we show a toast and switch to a safe tab
 */
export function switchTab(options: UniApp.SwitchTabOptions): void {
  const url = options.url || ''

  if (requiresAuth(url) && !isAuthenticated()) {
    uni.showToast({
      title: '请先登录',
      icon: 'none'
    })
    // Redirect to home tab instead of login (can't use navigateTo from tabBar)
    uni.switchTab({
      url: '/pages/index/index'
    })
    return
  }

  uni.switchTab({
    ...options,
    fail: (err) => {
      console.warn('switchTab failed:', err)
      options.fail?.(err as any)
    }
  })
}

/**
 * Handle login success - redirect to stored URL or default page
 */
export function handleLoginSuccess(defaultUrl = '/pages/index/index'): void {
  const redirectUrl = getStoredRedirect()

  if (redirectUrl) {
    // Check if redirect is to a tabBar page
    if (redirectUrl.startsWith('/pages/index/index') ||
        redirectUrl.startsWith('/pages/history/index') ||
        redirectUrl.startsWith('/pages/profile/index')) {
      uni.switchTab({
        url: redirectUrl,
        fail: () => {
          // If switchTab fails, try navigateTo
          uni.navigateTo({
            url: redirectUrl,
            fail: () => {
              // Final fallback - go to home
              uni.switchTab({ url: '/pages/index/index' })
            }
          })
        }
      })
    } else {
      uni.navigateTo({
        url: redirectUrl,
        fail: () => {
          // If navigateTo fails, try reLaunch
          uni.reLaunch({ url: redirectUrl })
        }
      })
    }
  } else {
    // No stored redirect, go to default
    uni.switchTab({
      url: defaultUrl,
      fail: () => {
        uni.reLaunch({ url: defaultUrl })
      }
    })
  }
}

/**
 * Initialize route guards on app startup
 * This function checks if the current page requires auth and redirects if needed
 */
export function initializeRouteGuard(): void {
  // Get current page path
  const pages = getCurrentPages()
  if (pages.length === 0) return

  const currentPage = pages[pages.length - 1]
  const currentPath = `/${currentPage.route}`

  // Check if current page requires auth
  if (requiresAuth(currentPath) && !isAuthenticated()) {
    console.log('RouteGuard: Protected page accessed without auth, redirecting to login')
    storeRedirect(currentPath)
    navigateToLogin()
  }
}

/**
 * Export wrapped navigation functions
 */
export const routeGuard = {
  navigateTo,
  redirectTo,
  reLaunch,
  switchTab,
  handleLoginSuccess,
  initializeRouteGuard,
  requiresAuth,
  isAuthenticated,
  getStoredRedirect
}

export default routeGuard
