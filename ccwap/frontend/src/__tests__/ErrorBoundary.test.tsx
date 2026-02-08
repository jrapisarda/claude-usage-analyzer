import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { ErrorBoundary } from '@/components/ErrorBoundary'

// A component that throws an error when shouldThrow is true
function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error message')
  }
  return <div>Child content</div>
}

describe('ErrorBoundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Suppress React's error boundary console output and capture calls
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <div>Normal content</div>
      </ErrorBoundary>
    )
    expect(screen.getByText('Normal content')).toBeInTheDocument()
  })

  it('renders multiple children normally', () => {
    render(
      <ErrorBoundary>
        <p>First child</p>
        <p>Second child</p>
      </ErrorBoundary>
    )
    expect(screen.getByText('First child')).toBeInTheDocument()
    expect(screen.getByText('Second child')).toBeInTheDocument()
  })

  it('shows error UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    // The default error UI heading
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('displays the error message from the thrown error', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('displays fallback message when error has no message', () => {
    function ThrowEmpty(): ReactNode {
      throw new Error('')
    }

    render(
      <ErrorBoundary>
        <ThrowEmpty />
      </ErrorBoundary>
    )
    // When error.message is empty string, the || fallback should show
    expect(screen.getByText('An unexpected error occurred')).toBeInTheDocument()
  })

  it('shows a Try Again button in the error UI', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Try Again')).toBeInTheDocument()
  })

  it('renders an AlertTriangle icon in the error UI', () => {
    const { container } = render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    // lucide AlertTriangle renders as SVG
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('resets error state when Try Again is clicked', async () => {
    const user = userEvent.setup()

    // Use a component that can switch between throwing and not throwing
    function Resetable() {
      // After error boundary resets, this will render without throwing
      return <div>Recovered content</div>
    }

    // First render: child throws
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()

    // Before clicking Try Again, swap child to a non-throwing one
    rerender(
      <ErrorBoundary>
        <Resetable />
      </ErrorBoundary>
    )

    // Error UI is still showing because hasError state is true
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()

    // Click Try Again to reset the error boundary
    await user.click(screen.getByText('Try Again'))

    // Now the ErrorBoundary should re-render children
    expect(screen.getByText('Recovered content')).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
  })

  it('renders custom fallback when provided', () => {
    const customFallback = <div>Custom error display</div>
    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )

    expect(screen.getByText('Custom error display')).toBeInTheDocument()
    // Default error UI should not be shown
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
    expect(screen.queryByText('Try Again')).not.toBeInTheDocument()
  })

  it('does not render custom fallback when no error occurs', () => {
    const customFallback = <div>Custom error display</div>
    render(
      <ErrorBoundary fallback={customFallback}>
        <div>Normal content</div>
      </ErrorBoundary>
    )

    expect(screen.getByText('Normal content')).toBeInTheDocument()
    expect(screen.queryByText('Custom error display')).not.toBeInTheDocument()
  })

  it('logs error to console via componentDidCatch', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    )

    // componentDidCatch calls console.error with 'ErrorBoundary caught:', error, errorInfo
    const boundaryCalls = consoleErrorSpy.mock.calls.filter(
      (call: unknown[]) => typeof call[0] === 'string' && call[0] === 'ErrorBoundary caught:'
    )
    expect(boundaryCalls.length).toBe(1)
    // Second argument should be the Error object
    expect(boundaryCalls[0][1]).toBeInstanceOf(Error)
    expect(boundaryCalls[0][1].message).toBe('Test error message')
    // Third argument should be the errorInfo object with componentStack
    expect(boundaryCalls[0][2]).toHaveProperty('componentStack')
  })

  it('does not show error UI for non-throwing children', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={false} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Child content')).toBeInTheDocument()
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument()
  })
})
