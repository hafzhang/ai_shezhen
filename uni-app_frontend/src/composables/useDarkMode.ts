/**
 * Dark Mode Composable
 * Handles dark mode detection, switching, and persistence
 */

import { ref, computed, onMounted, watch } from 'vue'

export type DarkModePreference = 'light' | 'dark' | 'auto'

const STORAGE_KEY = 'dark_mode_preference'

// Global state
const preference = ref<DarkModePreference>('auto')
const isDark = ref(false)

/**
 * Composable for dark mode functionality
 */
export function useDarkMode() {
  /**
   * Detect system dark mode preference
   */
  function detectSystemDarkMode(): boolean {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return false
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }

  /**
   * Get the effective dark mode state based on preference
   */
  function getEffectiveDarkMode(): boolean {
    if (preference.value === 'dark') {
      return true
    } else if (preference.value === 'light') {
      return false
    } else {
      // auto - use system preference
      return detectSystemDarkMode()
    }
  }

  /**
   * Load dark mode preference from storage
   */
  function loadPreference(): DarkModePreference {
    if (typeof localStorage === 'undefined') {
      return 'auto'
    }
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return (stored as DarkModePreference) || 'auto'
    } catch {
      return 'auto'
    }
  }

  /**
   * Save dark mode preference to storage
   */
  function savePreference(pref: DarkModePreference) {
    if (typeof localStorage === 'undefined') {
      return
    }
    try {
      localStorage.setItem(STORAGE_KEY, pref)
    } catch (error) {
      console.error('Failed to save dark mode preference:', error)
    }
  }

  /**
   * Update dark mode state and apply to DOM
   */
  function updateDarkMode() {
    const effective = getEffectiveDarkMode()
    isDark.value = effective

    // Apply dark mode class to HTML element for CSS targeting
    if (typeof document !== 'undefined') {
      if (effective) {
        document.documentElement.classList.add('dark-mode')
        document.documentElement.classList.remove('light-mode')
      } else {
        document.documentElement.classList.remove('dark-mode')
        document.documentElement.classList.add('light-mode')
      }
    }
  }

  /**
   * Set dark mode preference
   */
  function setDarkMode(pref: DarkModePreference) {
    preference.value = pref
    savePreference(pref)
    updateDarkMode()
  }

  /**
   * Toggle dark mode (cycles through light -> dark -> auto)
   */
  function toggleDarkMode() {
    if (preference.value === 'light') {
      setDarkMode('dark')
    } else if (preference.value === 'dark') {
      setDarkMode('auto')
    } else {
      setDarkMode('light')
    }
  }

  /**
   * Initialize dark mode on mount
   */
  function initialize() {
    // Load preference from storage
    preference.value = loadPreference()
    updateDarkMode()

    // Listen for system theme changes
    if (typeof window !== 'undefined' && window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      const handleChange = () => {
        if (preference.value === 'auto') {
          updateDarkMode()
        }
      }

      // Modern browsers
      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener('change', handleChange)
        return () => mediaQuery.removeEventListener('change', handleChange)
      }
      // Legacy browsers
      else if (mediaQuery.addListener) {
        mediaQuery.addListener(handleChange)
        return () => mediaQuery.removeListener(handleChange)
      }
    }
  }

  // Auto-initialize on first use
  if (typeof window !== 'undefined' && !window.__darkModeInitialized) {
    window.__darkModeInitialized = true
    onMounted(() => {
      const cleanup = initialize()
      // Store cleanup function for potential later use
      if (cleanup) {
        ;(window as any).__darkModeCleanup = cleanup
      }
    })
  }

  return {
    preference: computed(() => preference.value),
    isDark: computed(() => isDark.value),
    isLight: computed(() => !isDark.value),
    isAuto: computed(() => preference.value === 'auto'),
    setDarkMode,
    toggleDarkMode,
    detectSystemDarkMode,
    updateDarkMode
  }
}

// Extend Window interface for initialization flag
declare global {
  interface Window {
    __darkModeInitialized?: boolean
    __darkModeCleanup?: () => void
  }
}
