import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { TOKEN_COLORS } from '@/lib/chartConfig'
import { TOOLTIP_STYLE } from '@/lib/chartConfig'
import { formatNumber } from '@/lib/utils'

export interface TokenWaterfallTurn {
  turn_number: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_write_tokens: number
}

interface TokenWaterfallProps {
  turns: TokenWaterfallTurn[]
}

export function TokenWaterfall({ turns }: TokenWaterfallProps) {
  if (turns.length === 0) {
    return <p className="text-sm text-muted-foreground">No turn data available</p>
  }

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={turns} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <XAxis
            dataKey="turn_number"
            tick={{ fontSize: 10 }}
            stroke="var(--color-muted-foreground)"
            label={{ value: 'Turn', position: 'insideBottom', offset: -2, fontSize: 11, fill: 'var(--color-muted-foreground)' }}
          />
          <YAxis
            tick={{ fontSize: 10 }}
            stroke="var(--color-muted-foreground)"
            tickFormatter={(v: any) => formatNumber(v)}
            width={55}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            formatter={(value: any, name: any) => [formatNumber(value), name]}
            labelFormatter={(label: any) => `Turn ${label}`}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar
            dataKey="input_tokens"
            stackId="tokens"
            fill={TOKEN_COLORS.input}
            name="Input"
          />
          <Bar
            dataKey="output_tokens"
            stackId="tokens"
            fill={TOKEN_COLORS.output}
            name="Output"
          />
          <Bar
            dataKey="cache_read_tokens"
            stackId="tokens"
            fill={TOKEN_COLORS.cache_read}
            name="Cache Read"
          />
          <Bar
            dataKey="cache_write_tokens"
            stackId="tokens"
            fill={TOKEN_COLORS.cache_write}
            name="Cache Write"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
