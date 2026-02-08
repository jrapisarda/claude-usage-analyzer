import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageLayout } from '@/components/PageLayout'

describe('PageLayout', () => {
  it('renders the title', () => {
    render(<PageLayout title="Dashboard">Content</PageLayout>)
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders the title as an h2 element', () => {
    render(<PageLayout title="Dashboard">Content</PageLayout>)
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading).toHaveTextContent('Dashboard')
  })

  it('renders subtitle when provided', () => {
    render(
      <PageLayout title="Dashboard" subtitle="Overview of your usage">
        Content
      </PageLayout>
    )
    expect(screen.getByText('Overview of your usage')).toBeInTheDocument()
  })

  it('does not render subtitle when not provided', () => {
    render(<PageLayout title="Dashboard">Content</PageLayout>)
    // Only the heading and the children should be present
    const paragraphs = document.querySelectorAll('.text-sm.text-muted-foreground.mt-1')
    expect(paragraphs.length).toBe(0)
  })

  it('renders children content', () => {
    render(
      <PageLayout title="Test">
        <div data-testid="child-content">Hello world</div>
      </PageLayout>
    )
    expect(screen.getByTestId('child-content')).toBeInTheDocument()
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders multiple children', () => {
    render(
      <PageLayout title="Test">
        <p>First child</p>
        <p>Second child</p>
      </PageLayout>
    )
    expect(screen.getByText('First child')).toBeInTheDocument()
    expect(screen.getByText('Second child')).toBeInTheDocument()
  })

  it('applies correct styling classes to the wrapper', () => {
    const { container } = render(<PageLayout title="Test">Content</PageLayout>)
    const wrapper = container.firstElementChild
    expect(wrapper?.classList.contains('p-6')).toBe(true)
  })

  it('applies bold styling to the title', () => {
    render(<PageLayout title="Dashboard">Content</PageLayout>)
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading.classList.contains('font-bold')).toBe(true)
  })
})
