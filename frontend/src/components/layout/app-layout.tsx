import { Outlet } from 'react-router-dom'
import { Sidebar } from './sidebar'
import { Header } from './header'
import { useSidebarStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export function AppLayout() {
  const { isOpen } = useSidebarStore()

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div className={cn('transition-all duration-300', isOpen ? 'ml-64' : 'ml-16')}>
        <Header />
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
