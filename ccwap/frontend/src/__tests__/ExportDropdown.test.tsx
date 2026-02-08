import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExportDropdown } from '@/components/ExportDropdown'

// Mock useExport so we can verify export calls without triggering DOM download logic
const mockExportData = vi.fn()
vi.mock('@/hooks/useExport', () => ({
  useExport: () => ({ exportData: mockExportData }),
}))

describe('ExportDropdown', () => {
  const defaultProps = {
    page: 'sessions',
    getData: () => [{ id: 1, name: 'Alice' }],
  }

  beforeEach(() => {
    mockExportData.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders an export button', () => {
    render(<ExportDropdown {...defaultProps} />)
    const button = screen.getByTitle('Export data')
    expect(button).toBeInTheDocument()
    expect(button).toHaveTextContent('Export')
  })

  it('renders an SVG icon inside the button', () => {
    render(<ExportDropdown {...defaultProps} />)
    const button = screen.getByTitle('Export data')
    const svg = button.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })

  it('does not show dropdown options initially', () => {
    render(<ExportDropdown {...defaultProps} />)
    expect(screen.queryByText('Export CSV')).not.toBeInTheDocument()
    expect(screen.queryByText('Export JSON')).not.toBeInTheDocument()
  })

  it('opens dropdown with CSV and JSON options on click', async () => {
    const user = userEvent.setup()
    render(<ExportDropdown {...defaultProps} />)

    await user.click(screen.getByTitle('Export data'))

    expect(screen.getByText('Export CSV')).toBeInTheDocument()
    expect(screen.getByText('Export JSON')).toBeInTheDocument()
  })

  it('closes dropdown on second click of export button', async () => {
    const user = userEvent.setup()
    render(<ExportDropdown {...defaultProps} />)

    const button = screen.getByTitle('Export data')
    await user.click(button) // open
    expect(screen.getByText('Export CSV')).toBeInTheDocument()

    await user.click(button) // close
    expect(screen.queryByText('Export CSV')).not.toBeInTheDocument()
  })

  it('closes dropdown on outside click', async () => {
    const user = userEvent.setup()
    render(
      <div>
        <div data-testid="outside">Outside element</div>
        <ExportDropdown {...defaultProps} />
      </div>
    )

    // Open the dropdown
    await user.click(screen.getByTitle('Export data'))
    expect(screen.getByText('Export CSV')).toBeInTheDocument()

    // Click outside
    await user.click(screen.getByTestId('outside'))
    expect(screen.queryByText('Export CSV')).not.toBeInTheDocument()
  })

  it('calls getData and exportData with csv format when CSV option is selected', async () => {
    const user = userEvent.setup()
    const mockGetData = vi.fn().mockReturnValue([{ id: 1 }])
    render(<ExportDropdown page="sessions" getData={mockGetData} />)

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export CSV'))

    expect(mockGetData).toHaveBeenCalledTimes(1)
    expect(mockExportData).toHaveBeenCalledWith('csv', {
      page: 'sessions',
      data: [{ id: 1 }],
      columns: undefined,
      metadata: undefined,
    })
  })

  it('calls getData and exportData with json format when JSON option is selected', async () => {
    const user = userEvent.setup()
    const mockGetData = vi.fn().mockReturnValue([{ id: 1 }])
    render(<ExportDropdown page="sessions" getData={mockGetData} />)

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export JSON'))

    expect(mockGetData).toHaveBeenCalledTimes(1)
    expect(mockExportData).toHaveBeenCalledWith('json', {
      page: 'sessions',
      data: [{ id: 1 }],
      columns: undefined,
      metadata: undefined,
    })
  })

  it('passes columns and metadata to exportData when provided', async () => {
    const user = userEvent.setup()
    const columns = ['id', 'name']
    const metadata = { filter: 'active' }
    const getData = () => [{ id: 1, name: 'Test' }]

    render(
      <ExportDropdown
        page="test"
        getData={getData}
        columns={columns}
        metadata={metadata}
      />
    )

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export CSV'))

    expect(mockExportData).toHaveBeenCalledWith('csv', {
      page: 'test',
      data: [{ id: 1, name: 'Test' }],
      columns: ['id', 'name'],
      metadata: { filter: 'active' },
    })
  })

  it('does not call exportData when getData returns empty array', async () => {
    const user = userEvent.setup()
    const mockGetData = vi.fn().mockReturnValue([])
    render(<ExportDropdown page="sessions" getData={mockGetData} />)

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export CSV'))

    expect(mockGetData).toHaveBeenCalledTimes(1)
    expect(mockExportData).not.toHaveBeenCalled()
  })

  it('does not call exportData when getData returns empty array for JSON', async () => {
    const user = userEvent.setup()
    const mockGetData = vi.fn().mockReturnValue([])
    render(<ExportDropdown page="sessions" getData={mockGetData} />)

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export JSON'))

    expect(mockGetData).toHaveBeenCalledTimes(1)
    expect(mockExportData).not.toHaveBeenCalled()
  })

  it('closes dropdown after selecting an export format', async () => {
    const user = userEvent.setup()
    render(<ExportDropdown {...defaultProps} />)

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export CSV'))

    // Dropdown should be closed after export
    expect(screen.queryByText('Export CSV')).not.toBeInTheDocument()
    expect(screen.queryByText('Export JSON')).not.toBeInTheDocument()
  })

  it('keeps dropdown open when getData returns empty (early return before setOpen)', async () => {
    const user = userEvent.setup()
    const mockGetData = vi.fn().mockReturnValue([])
    render(<ExportDropdown page="sessions" getData={mockGetData} />)

    await user.click(screen.getByTitle('Export data'))
    await user.click(screen.getByText('Export JSON'))

    // handleExport returns early when data is empty, before calling setOpen(false)
    // so the dropdown remains visible
    expect(screen.getByText('Export CSV')).toBeInTheDocument()
    expect(screen.getByText('Export JSON')).toBeInTheDocument()
  })
})
