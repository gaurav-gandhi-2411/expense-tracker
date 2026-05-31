'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Menu, Plus } from 'lucide-react'
import { toast } from 'sonner'

import { Button, buttonVariants } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Separator } from '@/components/ui/separator'
import { createClient } from '@/lib/supabase/client'

interface NavProps {
  email: string
}

export function Nav({ email }: NavProps) {
  const router = useRouter()

  async function handleSignOut(): Promise<void> {
    const supabase = createClient()
    const { error } = await supabase.auth.signOut()
    if (error) {
      toast.error('Sign out failed')
      return
    }
    router.push('/sign-in')
    router.refresh()
  }

  return (
    <header className="border-b bg-background sticky top-0 z-50">
      <div className="container mx-auto px-4 flex items-center justify-between h-14">
        {/* Desktop nav — hidden below md */}
        <nav className="hidden md:flex items-center gap-6 w-full">
          {/* Left: brand */}
          <Link href="/expenses" className="font-semibold text-base">
            Expense Tracker
          </Link>

          {/* Center-right: links + actions */}
          <div className="flex items-center gap-4 ml-auto">
            <Link
              href="/expenses"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Expenses
            </Link>

            <Link
              href="/expenses/new"
              className={buttonVariants({ size: 'sm' })}
            >
              Add expense
            </Link>

            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button variant="ghost" size="sm" />}
              >
                {email}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={handleSignOut}>
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </nav>

        {/* Mobile nav — shown below md */}
        <div className="flex md:hidden items-center justify-between w-full">
          {/* Left: brand */}
          <span className="font-semibold text-base">Expense Tracker</span>

          {/* Right: + button + hamburger */}
          <div className="flex items-center gap-2">
            <Link
              href="/expenses/new"
              className={buttonVariants({ variant: 'ghost', size: 'icon-sm' })}
              aria-label="Add expense"
            >
              <Plus className="h-4 w-4" />
            </Link>

            <Sheet>
              <SheetTrigger
                render={
                  <Button variant="ghost" size="icon-sm" aria-label="Open menu" />
                }
              >
                <Menu className="h-4 w-4" />
              </SheetTrigger>
              <SheetContent side="left">
                <SheetHeader>
                  <SheetTitle>Expense Tracker</SheetTitle>
                </SheetHeader>
                <nav className="flex flex-col gap-1 mt-4 px-4">
                  <Link
                    href="/expenses"
                    className="text-sm py-2 hover:text-foreground text-muted-foreground transition-colors"
                  >
                    Expenses
                  </Link>
                  <Link
                    href="/expenses/new"
                    className="text-sm py-2 hover:text-foreground text-muted-foreground transition-colors"
                  >
                    Add expense
                  </Link>
                  <Separator className="my-3" />
                  <span className="text-xs text-muted-foreground truncate">{email}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="justify-start px-0 mt-1"
                    onClick={handleSignOut}
                  >
                    Sign out
                  </Button>
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </div>
    </header>
  )
}
