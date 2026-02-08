import { useState, useRef, useEffect } from 'react'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import { formatCurrency } from '@/lib/utils'

interface BudgetTrackerProps {
  spent: number
}

export function BudgetTracker({ spent }: BudgetTrackerProps) {
  const [budget, setBudget] = useLocalStorage('ccwap:monthly-budget', 0)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editing])

  const handleStartEdit = () => {
    setDraft(budget > 0 ? budget.toString() : '')
    setEditing(true)
  }

  const handleSave = () => {
    const parsed = parseFloat(draft)
    if (!isNaN(parsed) && parsed >= 0) {
      setBudget(parsed)
    }
    setEditing(false)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') setEditing(false)
  }

  const remaining = budget - spent
  const pct = budget > 0 ? (spent / budget) * 100 : 0
  const daysInMonth = new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate()
  const dayOfMonth = new Date().getDate()
  const burnRate = dayOfMonth > 0 ? spent / dayOfMonth : 0
  const projectedMonthly = burnRate * daysInMonth

  const barColor = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-yellow-500' : 'bg-green-500'

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h3 className="text-sm font-medium text-muted-foreground mb-3">Budget Tracker</h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
        <div>
          <span className="text-xs text-muted-foreground">Monthly Budget</span>
          {editing ? (
            <div className="flex items-center gap-1 mt-1">
              <span className="text-lg font-mono">$</span>
              <input
                ref={inputRef}
                type="number"
                min="0"
                step="0.01"
                value={draft}
                onChange={e => setDraft(e.target.value)}
                onBlur={handleSave}
                onKeyDown={handleKeyDown}
                className="font-mono text-lg w-28 bg-transparent border-b border-border outline-none focus:border-primary"
              />
            </div>
          ) : (
            <p
              className="font-mono text-lg cursor-pointer hover:text-primary transition-colors"
              onClick={handleStartEdit}
              title="Click to edit budget"
            >
              {budget > 0 ? formatCurrency(budget) : 'Set budget...'}
            </p>
          )}
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Spent</span>
          <p className="font-mono text-lg">{formatCurrency(spent)}</p>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Remaining</span>
          <p className={`font-mono text-lg ${budget > 0 && remaining < 0 ? 'text-red-500' : ''}`}>
            {budget > 0 ? formatCurrency(remaining) : '--'}
          </p>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Burn Rate</span>
          <p className="font-mono text-lg">{formatCurrency(burnRate)}/day</p>
          {budget > 0 && (
            <span className="text-xs text-muted-foreground">
              Projected: {formatCurrency(projectedMonthly)}
            </span>
          )}
        </div>
      </div>

      {budget > 0 && (
        <div>
          <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
            <span>{Math.min(pct, 100).toFixed(1)}% used</span>
            <span>{formatCurrency(spent)} / {formatCurrency(budget)}</span>
          </div>
          <div className="w-full h-3 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barColor}`}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
