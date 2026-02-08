import { Inbox } from 'lucide-react'

export function EmptyState({ message = 'No data available' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
      <Inbox className="h-8 w-8 mb-2" />
      <p>{message}</p>
    </div>
  )
}
