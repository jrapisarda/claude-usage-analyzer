import { AlertCircle } from 'lucide-react'

export function ErrorState({ message = 'Something went wrong' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-destructive">
      <AlertCircle className="h-8 w-8 mb-2" />
      <p>{message}</p>
    </div>
  )
}
