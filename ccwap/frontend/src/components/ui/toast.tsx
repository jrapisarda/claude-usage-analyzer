import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

const toastVariants = cva(
  'group pointer-events-auto relative flex w-full items-center justify-between space-x-2 overflow-hidden rounded-md border border-border p-4 pr-6 shadow-lg transition-all data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full',
  {
    variants: {
      variant: {
        default: 'border bg-background text-foreground',
        destructive:
          'destructive group border-destructive bg-destructive text-destructive-foreground',
        success:
          'border-green-500/50 bg-green-50 text-green-900 dark:bg-green-950 dark:text-green-100',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

export interface ToastData {
  id: string
  title?: string
  description?: string
  variant?: 'default' | 'destructive' | 'success'
  duration?: number
}

interface ToastProps extends React.HTMLAttributes<HTMLDivElement>,
  VariantProps<typeof toastVariants> {
  onClose?: () => void
}

const Toast = React.forwardRef<HTMLDivElement, ToastProps>(
  ({ className, variant, children, onClose, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(toastVariants({ variant }), className)}
        {...props}
      >
        <div className="flex-1">{children}</div>
        {onClose && (
          <button
            onClick={onClose}
            className="absolute right-1 top-1 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity hover:text-foreground focus:opacity-100 focus:outline-none group-hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    )
  }
)
Toast.displayName = 'Toast'

function ToastTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('text-sm font-semibold [&+div]:text-xs', className)}
      {...props}
    />
  )
}
ToastTitle.displayName = 'ToastTitle'

function ToastDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('text-sm opacity-90', className)}
      {...props}
    />
  )
}
ToastDescription.displayName = 'ToastDescription'

// Simple toast state management
type ToastListener = (toasts: ToastData[]) => void

let toasts: ToastData[] = []
let listeners: ToastListener[] = []
let idCounter = 0

function emitChange() {
  for (const listener of listeners) {
    listener([...toasts])
  }
}

export function toast(data: Omit<ToastData, 'id'>) {
  const id = String(++idCounter)
  const newToast: ToastData = { id, duration: 5000, ...data }
  toasts = [...toasts, newToast]
  emitChange()

  if (newToast.duration && newToast.duration > 0) {
    setTimeout(() => {
      dismissToast(id)
    }, newToast.duration)
  }

  return id
}

export function dismissToast(id: string) {
  toasts = toasts.filter(t => t.id !== id)
  emitChange()
}

export function useToasts() {
  const [state, setState] = React.useState<ToastData[]>([])

  React.useEffect(() => {
    listeners.push(setState)
    return () => {
      listeners = listeners.filter(l => l !== setState)
    }
  }, [])

  return state
}

export { Toast, ToastTitle, ToastDescription, toastVariants }
