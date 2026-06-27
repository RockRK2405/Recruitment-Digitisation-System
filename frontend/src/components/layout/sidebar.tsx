import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useSidebarStore } from '@/lib/store'
import {
  LayoutDashboard,
  Users,
  Briefcase,
  GitCompare,
  FileText,
  BarChart3,
  Bot,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react'

interface NavItem {
  title: string
  href: string
  icon: React.ElementType
  badge?: string
}

const navItems: NavItem[] = [
  { title: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { title: 'Candidates', href: '/candidates', icon: Users },
  { title: 'Job Descriptions', href: '/jobs', icon: Briefcase },
  { title: 'AI Matching', href: '/matching', icon: GitCompare, badge: 'AI' },
  { title: 'Resume Intelligence', href: '/resumes', icon: FileText },
  { title: 'Analytics', href: '/analytics', icon: BarChart3 },
  { title: 'AI Agent', href: '/agent', icon: Bot, badge: 'NEW' },
]

import { Settings } from 'lucide-react'
const bottomNavItems: NavItem[] = [
  { title: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const { isOpen, toggle } = useSidebarStore()
  const location = useLocation()

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r bg-sidebar transition-all duration-300',
        isOpen ? 'w-64' : 'w-16'
      )}
    >
      <div className={cn('flex h-16 items-center border-b border-sidebar-border px-4', !isOpen && 'justify-center')}>
        {isOpen ? (
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </div>
            <div>
              <p className="text-sm font-semibold text-sidebar-foreground">WorkforceAI</p>
              <p className="text-[10px] text-muted-foreground">Recruitment Intelligence</p>
            </div>
          </div>
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-1 p-3">
        <TooltipProvider delayDuration={0}>
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.href)
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <NavLink
                    to={item.href}
                    className={cn(
                      'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground'
                    )}
                  >
                    <item.icon className={cn('h-5 w-5 shrink-0', isActive && 'text-primary')} />
                    {isOpen && (
                      <>
                        <span className="flex-1 truncate">{item.title}</span>
                        {item.badge && (
                          <span className={cn(
                            'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold',
                            item.badge === 'AI' ? 'bg-accent/15 text-accent' : 'bg-primary/15 text-primary'
                          )}>
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </TooltipTrigger>
                {!isOpen && (
                  <TooltipContent side="right" className="flex items-center gap-2">
                    <span>{item.title}</span>
                    {item.badge && (
                      <span className={cn(
                        'inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold',
                        item.badge === 'AI' ? 'bg-accent/15 text-accent' : 'bg-primary/15 text-primary'
                      )}>
                        {item.badge}
                      </span>
                    )}
                  </TooltipContent>
                )}
              </Tooltip>
            )
          })}
        </TooltipProvider>
      </nav>

      <div className="border-t border-sidebar-border p-3 space-y-1">
        <TooltipProvider delayDuration={0}>
          {bottomNavItems.map((item) => {
            const isActive = location.pathname.startsWith(item.href)
            return (
              <Tooltip key={item.href}>
                <TooltipTrigger asChild>
                  <NavLink
                    to={item.href}
                    className={cn(
                      'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-foreground'
                    )}
                  >
                    <item.icon className={cn('h-5 w-5 shrink-0', isActive && 'text-primary')} />
                    {isOpen && <span className="flex-1 truncate">{item.title}</span>}
                  </NavLink>
                </TooltipTrigger>
                {!isOpen && <TooltipContent side="right">{item.title}</TooltipContent>}
              </Tooltip>
            )
          })}
        </TooltipProvider>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggle}
          className="w-full text-sidebar-foreground/60 hover:text-sidebar-foreground"
        >
          {isOpen ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </Button>
      </div>
    </aside>
  )
}
