import { createI18n } from 'vue-i18n'
import zhCN from './zh-CN'
import enUS from './en-US'

export type MessageSchema = typeof zhCN

export const SUPPORT_LOCALES = {
  'zh-CN': '简体中文',
  'en-US': 'English',
} as const

export type SupportedLocale = keyof typeof SUPPORT_LOCALES

const STORAGE_KEY = 'app_language'

/**
 * Get language from localStorage
 */
export function getStoredLocale(): SupportedLocale {
  if (typeof window === 'undefined') return 'zh-CN'

  try {
    const stored = localStorage.getItem(STORAGE_KEY) as SupportedLocale
    if (stored && SUPPORT_LOCALES[stored]) {
      return stored
    }
  } catch {
    // Ignore storage errors
  }

  // Try to detect browser language
  const browserLang = navigator.language
  if (browserLang.startsWith('zh')) {
    return 'zh-CN'
  } else if (browserLang.startsWith('en')) {
    return 'en-US'
  }

  return 'zh-CN'
}

/**
 * Save language to localStorage
 */
export function setStoredLocale(locale: SupportedLocale) {
  if (typeof window === 'undefined') return

  try {
    localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // Ignore storage errors
  }
}

// Create i18n instance
const i18n = createI18n<[MessageSchema], SupportedLocale>({
  // Use Composition API mode
  legacy: false,

  // Default locale
  locale: getStoredLocale(),

  // Fallback locale
  fallbackLocale: 'zh-CN',

  // Available locales
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },

  // Global injection
  globalInjection: true,
})

export default i18n
