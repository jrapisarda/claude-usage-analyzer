import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MetricCard } from '@/components/ui/MetricCard'

describe('MetricCard', () => {
  it('renders title and value', () => {
    render(<MetricCard title="Total Cost" value="$12.50" />)
    expect(screen.getByText('Total Cost')).toBeInTheDocument()
    expect(screen.getByText('$12.50')).toBeInTheDocument()
  })

  it('renders subtitle when provided', () => {
    render(<MetricCard title="Sessions" value="42" subtitle="Last 30 days" />)
    expect(screen.getByText('Last 30 days')).toBeInTheDocument()
  })

  it('does not render subtitle when not provided', () => {
    render(<MetricCard title="Sessions" value="42" />)
    // The subtitle paragraph should not exist
    const subtitleElements = document.querySelectorAll('.text-xs.text-muted-foreground.mt-1')
    expect(subtitleElements.length).toBe(0)
  })

  it('renders up trend indicator', () => {
    const { container } = render(<MetricCard title="Cost" value="$5.00" trend="up" />)
    // Up arrow: Unicode 9650 (black up-pointing triangle)
    const upArrow = container.querySelector('.text-green-500')
    expect(upArrow).toBeInTheDocument()
    expect(upArrow?.textContent).toContain('\u25B2')
  })

  it('renders down trend indicator', () => {
    const { container } = render(<MetricCard title="Cost" value="$5.00" trend="down" />)
    // Down arrow: Unicode 9660 (black down-pointing triangle)
    const downArrow = container.querySelector('.text-red-500')
    expect(downArrow).toBeInTheDocument()
    expect(downArrow?.textContent).toContain('\u25BC')
  })

  it('does not render trend indicator when trend is neutral', () => {
    const { container } = render(<MetricCard title="Cost" value="$5.00" trend="neutral" />)
    expect(container.querySelector('.text-green-500')).not.toBeInTheDocument()
    expect(container.querySelector('.text-red-500')).not.toBeInTheDocument()
  })

  it('does not render trend indicator when trend is not provided', () => {
    const { container } = render(<MetricCard title="Cost" value="$5.00" />)
    expect(container.querySelector('.text-green-500')).not.toBeInTheDocument()
    expect(container.querySelector('.text-red-500')).not.toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<MetricCard title="Test" value="0" className="custom-class" />)
    expect(container.firstElementChild?.classList.contains('custom-class')).toBe(true)
  })
})
