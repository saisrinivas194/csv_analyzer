import React from 'react';
import { Users, UserCheck, DollarSign, TrendingUp } from 'lucide-react';

const KPIAnalysis = ({ data }) => {
  if (!data) {
    return (
      <div className="card">
        <h2>KPI Analysis</h2>
        <p>No analysis data available.</p>
      </div>
    );
  }

  const metrics = [
    {
      icon: <Users size={20} />,
      label: 'Total Customers',
      value: data.totalCustomers || 0,
      color: '#2563eb'
    },
    {
      icon: <UserCheck size={20} />,
      label: 'Active Customers',
      value: data.activeCustomers || 0,
      color: '#16a34a'
    },
    {
      icon: <DollarSign size={20} />,
      label: 'Average Order Value',
      value: typeof data.averageOrderValue === 'number' ? data.averageOrderValue.toFixed(2) : data.averageOrderValue,
      color: '#d97706'
    },
    {
      icon: <TrendingUp size={20} />,
      label: 'Activity Rate',
      value: typeof data.activityRate === 'number' ? `${data.activityRate.toFixed(1)}%` : `${data.activityRate}%`,
      color: '#dc2626'
    }
  ];

  return (
    <div className="card">
      <h2>KPI Analysis</h2>
      <div className="metric-grid">
        {metrics.map((metric, index) => (
          <div key={index} className="metric-card">
            <div className="metric-icon" style={{ color: metric.color }}>{metric.icon}</div>
            <div className="metric-value">{metric.value}</div>
            <div className="metric-label">{metric.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default KPIAnalysis;
