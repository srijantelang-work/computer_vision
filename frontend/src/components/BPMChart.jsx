import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { Activity } from 'lucide-react';
import './BPMChart.css';

export default function BPMChart({ chunks }) {
  if (!chunks || chunks.length === 0) return null;

  // Filter valid chunks and format data for Recharts
  const data = chunks
    .filter(c => c.bpm !== null)
    .map(c => ({
      time: c.time_label,
      bpm: c.bpm,
      sqi: c.sqi,
    }));

  if (data.length === 0) return null;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="custom-tooltip glass-panel">
          <p className="tooltip-label">{`Time: ${label}`}</p>
          <p className="tooltip-bpm text-accent">
            {`Heart Rate: ${payload[0].value} BPM`}
          </p>
          {payload[1] && (
            <p className="tooltip-sqi text-secondary">
              {`Signal Quality: ${(payload[1].value * 100).toFixed(0)}%`}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bpm-chart-container glass-panel animate-fade-in" style={{ animationDelay: '0.2s' }}>
      <div className="chart-header">
        <Activity size={20} className="text-accent" />
        <h3>Heart Rate Trend</h3>
      </div>
      
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart
            data={data}
            margin={{ top: 20, right: 30, left: 0, bottom: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
            <XAxis 
              dataKey="time" 
              stroke="var(--text-tertiary)" 
              tick={{ fill: 'var(--text-tertiary)', fontSize: 12 }}
              tickMargin={10}
            />
            <YAxis 
              yAxisId="left"
              domain={['dataMin - 5', 'dataMax + 5']}
              stroke="var(--text-tertiary)"
              tick={{ fill: 'var(--text-tertiary)', fontSize: 12 }}
              tickFormatter={(value) => `${Math.round(value)}`}
            />
            <YAxis 
              yAxisId="right"
              orientation="right"
              domain={[0, 1]}
              hide={true} // Hidden axis for SQI
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '10px' }} />
            <Line 
              yAxisId="left"
              type="monotone" 
              dataKey="bpm" 
              name="Heart Rate (BPM)"
              stroke="var(--accent-primary)" 
              strokeWidth={3}
              dot={{ r: 4, fill: 'var(--bg-primary)', strokeWidth: 2 }}
              activeDot={{ r: 6, fill: 'var(--accent-primary)' }}
            />
            <Line 
              yAxisId="right"
              type="monotone" 
              dataKey="sqi" 
              name="Signal Quality"
              stroke="var(--text-tertiary)" 
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
