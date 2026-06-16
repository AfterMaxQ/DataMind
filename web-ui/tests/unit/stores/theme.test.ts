import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { setActivePinia, createPinia } from 'pinia'
import { useThemeStore } from '@/stores/theme'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value }),
    removeItem: vi.fn((key: string) => { delete store[key] }),
    clear: vi.fn(() => { store = {} }),
  }
})()

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

describe('Theme Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorageMock.clear()
    // Reset document theme attribute
    document.documentElement.removeAttribute('data-theme')
  })

  it('defaults to light theme when no preference stored', () => {
    const store = useThemeStore()
    expect(store.theme).toBe('light')
  })

  it('toggles from light to dark', () => {
    const store = useThemeStore()
    store.setTheme('light')
    store.toggle()
    expect(store.theme).toBe('dark')
  })

  it('toggles from dark to light', () => {
    const store = useThemeStore()
    store.setTheme('dark')
    store.toggle()
    expect(store.theme).toBe('light')
  })

  it('persists theme preference to localStorage', async () => {
    const store = useThemeStore()
    store.setTheme('dark')
    await nextTick()
    expect(localStorageMock.setItem).toHaveBeenCalledWith('datamind-theme', 'dark')
  })

  it('sets data-theme attribute on document root', async () => {
    const store = useThemeStore()
    store.setTheme('dark')
    await nextTick()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})
