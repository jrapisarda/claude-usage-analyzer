import {
  Toast,
  ToastTitle,
  ToastDescription,
  useToasts,
  dismissToast,
} from '@/components/ui/toast'

export function Toaster() {
  const toasts = useToasts()

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col-reverse md:max-w-[420px]">
      {toasts.map((t) => (
        <Toast
          key={t.id}
          variant={t.variant}
          onClose={() => dismissToast(t.id)}
          className="mb-2"
        >
          {t.title && <ToastTitle>{t.title}</ToastTitle>}
          {t.description && (
            <ToastDescription>{t.description}</ToastDescription>
          )}
        </Toast>
      ))}
    </div>
  )
}
