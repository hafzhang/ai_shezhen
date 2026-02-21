import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { SUPPORT_LOCALES, setStoredLocale, getStoredLocale, type SupportedLocale } from '@/locales'

export function useLanguage() {
  const { locale, availableLocales } = useI18n()

  // Current locale state
  const currentLocale = ref<SupportedLocale>(getStoredLocale())

  // Computed properties
  const isZhCN = computed(() => currentLocale.value === 'zh-CN')
  const isEnUS = computed(() => currentLocale.value === 'en-US')

  // Get locale display name
  const localeDisplayName = computed(() => SUPPORT_LOCALES[currentLocale.value])

  // Available locales list
  const availableLocalesList = computed(() =>
    Object.entries(SUPPORT_LOCALES).map(([code, name]) => ({
      code: code as SupportedLocale,
      name,
    }))
  )

  /**
   * Set language
   */
  function setLanguage(newLocale: SupportedLocale) {
    if (!SUPPORT_LOCALES[newLocale]) {
      console.warn(`Unsupported locale: ${newLocale}`)
      return
    }

    currentLocale.value = newLocale
    locale.value = newLocale
    setStoredLocale(newLocale)
  }

  /**
   * Toggle language (between zh-CN and en-US)
   */
  function toggleLanguage() {
    const newLocale: SupportedLocale = currentLocale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
    setLanguage(newLocale)
  }

  /**
   * Initialize language from storage
   */
  function initializeLanguage() {
    const storedLocale = getStoredLocale()
    currentLocale.value = storedLocale
    locale.value = storedLocale
  }

  // Watch for locale changes and sync with i18n
  watch(currentLocale, (newLocale) => {
    locale.value = newLocale
  })

  return {
    currentLocale,
    isZhCN,
    isEnUS,
    localeDisplayName,
    availableLocalesList,
    setLanguage,
    toggleLanguage,
    initializeLanguage,
  }
}
