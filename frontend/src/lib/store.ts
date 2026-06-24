import { create } from 'zustand'
import type { User } from '@/types'

interface AuthStore {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  setAuth: (user: User, token: string) => void
  logout: () => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  setAuth: (user, token) => {
    localStorage.setItem('token', token)
    set({ user, token, isAuthenticated: true, isLoading: false })
  },
  logout: () => {
    localStorage.removeItem('token')
    set({ user: null, token: null, isAuthenticated: false, isLoading: false })
  },
  setLoading: (loading) => set({ isLoading: loading }),
}))

interface ThemeStore {
  isDark: boolean
  toggle: () => void
  setDark: (val: boolean) => void
}

export const useThemeStore = create<ThemeStore>((set) => ({
  isDark: true,
  toggle: () => {
    set((state) => {
      const newDark = !state.isDark
      document.documentElement.classList.toggle('dark', newDark)
      return { isDark: newDark }
    })
  },
  setDark: (val) => {
    document.documentElement.classList.toggle('dark', val)
    set({ isDark: val })
  },
}))

interface SidebarStore {
  isOpen: boolean
  toggle: () => void
  setOpen: (val: boolean) => void
}

export const useSidebarStore = create<SidebarStore>((set) => ({
  isOpen: true,
  toggle: () => set((state) => ({ isOpen: !state.isOpen })),
  setOpen: (val) => set({ isOpen: val }),
}))
