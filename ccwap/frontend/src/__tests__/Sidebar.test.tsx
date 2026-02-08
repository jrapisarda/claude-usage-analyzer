import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { Sidebar } from '@/components/Sidebar'

function renderSidebar(initialEntries: string[] = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Sidebar />
    </MemoryRouter>
  )
}

describe('Sidebar', () => {
  it('renders the CCWAP heading', () => {
    renderSidebar()
    expect(screen.getByText('CCWAP')).toBeInTheDocument()
  })

  it('renders the subtitle', () => {
    renderSidebar()
    expect(screen.getByText('Claude Code Analytics')).toBeInTheDocument()
  })

  it('renders all 8 nav items', () => {
    renderSidebar()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Projects')).toBeInTheDocument()
    expect(screen.getByText('Cost Analysis')).toBeInTheDocument()
    expect(screen.getByText('Productivity')).toBeInTheDocument()
    expect(screen.getByText('Deep Analytics')).toBeInTheDocument()
    expect(screen.getByText('Experiments')).toBeInTheDocument()
    expect(screen.getByText('Live Monitor')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders nav items as links', () => {
    renderSidebar()
    const links = screen.getAllByRole('link')
    expect(links.length).toBe(8)
  })

  it('links point to the correct paths', () => {
    renderSidebar()
    const links = screen.getAllByRole('link')
    const hrefs = links.map(link => link.getAttribute('href'))
    expect(hrefs).toEqual([
      '/', '/projects', '/cost', '/productivity',
      '/analytics', '/experiments', '/live', '/settings',
    ])
  })

  it('highlights the active nav item based on current route', () => {
    renderSidebar(['/projects'])
    const projectsLink = screen.getByText('Projects').closest('a')
    // Active link should have bg-accent class
    expect(projectsLink?.classList.contains('bg-accent')).toBe(true)
  })

  it('does not highlight non-active nav items', () => {
    renderSidebar(['/'])
    const projectsLink = screen.getByText('Projects').closest('a')
    expect(projectsLink?.classList.contains('bg-accent')).toBe(false)
  })

  it('renders an SVG icon for each nav item', () => {
    renderSidebar()
    const links = screen.getAllByRole('link')
    for (const link of links) {
      const svg = link.querySelector('svg')
      expect(svg).toBeInTheDocument()
    }
  })
})
