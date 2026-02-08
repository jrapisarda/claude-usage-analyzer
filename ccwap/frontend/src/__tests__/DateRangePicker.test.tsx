import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DateRangePicker } from '@/components/DateRangePicker'
import { presets } from '@/hooks/useDateRange'

describe('DateRangePicker', () => {
  const defaultProps = {
    preset: 'last-30-days' as const,
    dateRange: { from: '2025-01-01', to: '2025-01-31' },
    onPresetChange: vi.fn(),
    onDateChange: vi.fn(),
  }

  it('renders all 8 preset buttons', () => {
    render(<DateRangePicker {...defaultProps} />)

    for (const p of presets) {
      expect(screen.getByText(p.label)).toBeInTheDocument()
    }
  })

  it('renders buttons with correct preset labels', () => {
    render(<DateRangePicker {...defaultProps} />)

    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Yesterday')).toBeInTheDocument()
    expect(screen.getByText('This Week')).toBeInTheDocument()
    expect(screen.getByText('Last Week')).toBeInTheDocument()
    expect(screen.getByText('Last 30 Days')).toBeInTheDocument()
    expect(screen.getByText('This Month')).toBeInTheDocument()
    expect(screen.getByText('Last Month')).toBeInTheDocument()
    expect(screen.getByText('All Time')).toBeInTheDocument()
  })

  it('calls onPresetChange when a preset button is clicked', async () => {
    const user = userEvent.setup()
    const onPresetChange = vi.fn()
    render(<DateRangePicker {...defaultProps} onPresetChange={onPresetChange} />)

    await user.click(screen.getByText('Today'))
    expect(onPresetChange).toHaveBeenCalledWith('today')
  })

  it('calls onPresetChange with the correct preset value for each button', async () => {
    const user = userEvent.setup()
    const onPresetChange = vi.fn()
    render(<DateRangePicker {...defaultProps} onPresetChange={onPresetChange} />)

    await user.click(screen.getByText('Yesterday'))
    expect(onPresetChange).toHaveBeenCalledWith('yesterday')

    await user.click(screen.getByText('All Time'))
    expect(onPresetChange).toHaveBeenCalledWith('all-time')
  })

  it('highlights the currently selected preset button', () => {
    render(<DateRangePicker {...defaultProps} preset="today" />)

    const todayButton = screen.getByText('Today')
    // Active preset gets bg-primary class
    expect(todayButton.classList.contains('bg-primary')).toBe(true)

    const yesterdayButton = screen.getByText('Yesterday')
    expect(yesterdayButton.classList.contains('bg-primary')).toBe(false)
    expect(yesterdayButton.classList.contains('bg-secondary')).toBe(true)
  })

  it('highlights Last 30 Days when that is the active preset', () => {
    render(<DateRangePicker {...defaultProps} preset="last-30-days" />)

    const activeButton = screen.getByText('Last 30 Days')
    expect(activeButton.classList.contains('bg-primary')).toBe(true)
  })

  it('shows no highlighted button when preset is null', () => {
    render(<DateRangePicker {...defaultProps} preset={null} />)

    // All buttons should have the inactive class
    const buttons = screen.getAllByRole('button')
    for (const button of buttons) {
      expect(button.classList.contains('bg-secondary')).toBe(true)
      expect(button.classList.contains('bg-primary')).toBe(false)
    }
  })
})
