import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LoadingState } from '@/components/ui/LoadingState'
import { ErrorState } from '@/components/ui/ErrorState'
import { EmptyState } from '@/components/ui/EmptyState'

describe('LoadingState', () => {
  it('renders default loading message', () => {
    render(<LoadingState />)
    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('renders custom loading message', () => {
    render(<LoadingState message="Fetching data..." />)
    expect(screen.getByText('Fetching data...')).toBeInTheDocument()
  })

  it('renders the spinner element', () => {
    const { container } = render(<LoadingState />)
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })
})

describe('ErrorState', () => {
  it('renders default error message', () => {
    render(<ErrorState />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders custom error message', () => {
    render(<ErrorState message="Failed to load sessions" />)
    expect(screen.getByText('Failed to load sessions')).toBeInTheDocument()
  })

  it('renders AlertCircle icon', () => {
    const { container } = render(<ErrorState />)
    // lucide-react renders SVG elements
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('has destructive styling', () => {
    const { container } = render(<ErrorState />)
    const wrapper = container.firstElementChild
    expect(wrapper?.classList.contains('text-destructive')).toBe(true)
  })
})

describe('EmptyState', () => {
  it('renders default empty message', () => {
    render(<EmptyState />)
    expect(screen.getByText('No data available')).toBeInTheDocument()
  })

  it('renders custom empty message', () => {
    render(<EmptyState message="No sessions found" />)
    expect(screen.getByText('No sessions found')).toBeInTheDocument()
  })

  it('renders Inbox icon', () => {
    const { container } = render(<EmptyState />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('has muted foreground styling', () => {
    const { container } = render(<EmptyState />)
    const wrapper = container.firstElementChild
    expect(wrapper?.classList.contains('text-muted-foreground')).toBe(true)
  })
})
