// src/pages/Dashboard.js
import React, { useState, useEffect } from 'react';
import api from '../services/api';

const Dashboard = () => {
  const [apiStatus, setApiStatus] = useState('checking...');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await api.get('/health');
        if (response.data.status === 'ok') {
          setApiStatus('OK');
        } else {
          setApiStatus('Error');
        }
      } catch (err) {
        setApiStatus('Unreachable');
      }
    };
    checkHealth();
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <p>Welcome to the LSP Apparel Management System.</p>
      <p>Use the navigation above to manage cloth, designs, and production.</p>
      <br />
      <p>API Status: <b style={{color: apiStatus === 'OK' ? 'var(--success-color)' : 'var(--danger-color)'}}>{apiStatus}</b></p>
    </div>
  );
};

export default Dashboard;