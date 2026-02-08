import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { useNavigate } from 'react-router'
import { formatCurrency } from '@/lib/utils'

interface TreeNode {
  session_id: string
  project_display: string
  user_type: string
  total_cost: number
  children: TreeNode[]
}

interface AgentTreeViewProps {
  trees: TreeNode[]
}

function TreeNodeItem({ node, depth = 0 }: { node: TreeNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth === 0)
  const navigate = useNavigate()
  const hasChildren = node.children.length > 0
  const isAgent = node.user_type === 'agent'

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1.5 px-2 rounded hover:bg-accent/50 text-sm cursor-pointer"
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => hasChildren ? setExpanded(!expanded) : navigate(`/sessions/${node.session_id}`)}
      >
        {hasChildren ? (
          <button onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }} className="p-0.5">
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        ) : <span className="w-4" />}

        {isAgent && (
          <span className="px-1.5 py-0.5 text-[10px] font-medium bg-purple-500/20 text-purple-400 rounded">
            agent
          </span>
        )}

        <span
          className="text-xs font-mono text-muted-foreground hover:text-foreground hover:underline"
          onClick={(e) => { e.stopPropagation(); navigate(`/sessions/${node.session_id}`) }}
        >
          {node.session_id.slice(0, 8)}...
        </span>
        <span className="text-xs truncate">{node.project_display}</span>
        <span className="text-xs text-muted-foreground ml-auto">{formatCurrency(node.total_cost)}</span>
      </div>

      {expanded && hasChildren && (
        <div>
          {node.children.map(child => (
            <TreeNodeItem key={child.session_id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export function AgentTreeView({ trees }: AgentTreeViewProps) {
  if (trees.length === 0) {
    return <p className="text-sm text-muted-foreground">No agent session trees found</p>
  }

  return (
    <div className="space-y-1">
      {trees.map(tree => (
        <TreeNodeItem key={tree.session_id} node={tree} />
      ))}
    </div>
  )
}
