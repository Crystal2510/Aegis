import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const data = [
  { name: 'Jan', trust: 80 },
  { name: 'Feb', trust: 85 },
  { name: 'Mar', trust: 82 },
  { name: 'Apr', trust: 89 },
  { name: 'May', trust: 94 },
  { name: 'Current', trust: 70 }, // Simulating a drop on this upload
];

const FinancialDNAGraph = () => {
  return (
    <div className="panel-glass p-6 h-[250px] flex flex-col">
      <h3 className="text-sm font-semibold tracking-wider text-gray-400 mb-4 uppercase">
        Financial DNA (Trust Score)
      </h3>
      <div className="flex-1 w-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis 
              dataKey="name" 
              stroke="#94A3B8" 
              fontSize={12} 
              tickLine={false}
              axisLine={false}
            />
            <YAxis 
              stroke="#94A3B8" 
              fontSize={12} 
              domain={[0, 100]} 
              tickLine={false}
              axisLine={false}
            />
            <Tooltip 
              contentStyle={{ backgroundColor: '#112240', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
              itemStyle={{ color: '#0F9490' }}
            />
            <Line 
              type="monotone" 
              dataKey="trust" 
              stroke="#00C853" 
              strokeWidth={3}
              dot={{ fill: '#00C853', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default FinancialDNAGraph;
