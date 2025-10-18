// src/pages/ProductionPage.js
import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const ProductionPage = () => {
  const [inProgress, setInProgress] = useState([]);
  const [designs, setDesigns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { hasAccess } = useAuth();

  // Form state
  const [designId, setDesignId] = useState('');
  const [stage, setStage] = useState('cutting');

  const fetchAllData = async () => {
    setLoading(true);
    setError('');
    try {
      const [progressRes, designsRes] = await Promise.all([
        api.get('/production/in-progress'),
        api.post('/designs/operate', { action: 'READ_ALL' })
      ]);
      setInProgress(progressRes.data);
      setDesigns(designsRes.data);
      if (designsRes.data.length > 0) {
        setDesignId(designsRes.data[0].id); // Default to first design
      }
    } catch (err) {
      setError('Failed to fetch production data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const handleStartStage = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.post('/production/add', {
        design_id: designId,
        stage: stage,
      });
      fetchAllData(); // Refresh
    } catch (err) {
      setError('Failed to start stage. ' + (err.response?.data?.detail || 'Check validations.'));
    }
  };

  const handleCompleteStage = async (tracking_id) => {
    setError('');
    try {
      await api.patch(`/production/${tracking_id}/complete`);
      fetchAllData(); // Refresh
    } catch (err) {
      setError('Failed to complete stage. ' + (err.response?.data?.detail || ''));
    }
  };
  
  const handleDeleteTracking = async (tracking_id) => {
    if (!window.confirm('Are you sure you want to delete this tracking record?')) {
      return;
    }
    setError('');
    try {
      await api.delete(`/production/${tracking_id}`);
      fetchAllData(); // Refresh
    } catch (err) {
      setError('Failed to delete record. ' + (err.response?.data?.detail || ''));
    }
  };

  return (
    <div>
      <h2>Start New Production Stage</h2>
      <form onSubmit={handleStartStage} style={{ display: 'flex', gap: '15px', marginBottom: '20px' }}>
        <div className="form-group">
          <label>Design</label>
          <select value={designId} onChange={(e) => setDesignId(e.target.value)} required>
            <option value="" disabled>Select Design</option>
            {designs.map(d => (
              <option key={d.id} value={d.id}>{d.design_code} ({d.id})</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label>Stage</label>
          <select value={stage} onChange={(e) => setStage(e.target.value)} required>
            <option value="cutting">Cutting</option>
            <option value="sewing">Sewing</option>
            <option value="ironing">Ironing</option>
          </select>
        </div>
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <button type="submit" className="btn btn-primary">Start Stage</button>
        </div>
      </form>
      {error && <p className="error-message">{error}</p>}

      <hr style={{ margin: '20px 0', borderColor: 'var(--border-color)'}} />

      <h2>All In-Progress Items</h2>
      {loading ? <p>Loading...</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Tracking ID</th>
              <th>Design ID</th>
              <th>Stage</th>
              <th>Status</th>
              <th>Arrived At</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {inProgress.map((item) => (
              <tr key={item.id}>
                <td>{item.id}</td>
                <td>{item.design_id}</td>
                <td>{item.stage}</td>
                <td>{item.status}</td>
                <td>{new Date(item.arrived_at).toLocaleString()}</td>
                <td>
                  <button onClick={() => handleCompleteStage(item.id)} className="btn btn-primary" style={{backgroundColor: 'var(--success-color)'}}>
                    Mark Complete
                  </button>
                  {hasAccess(2) && (
                    <button onClick={() => handleDeleteTracking(item.id)} className="btn btn-danger" style={{marginLeft: '5px'}}>
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p style={{marginTop: '10px', color: 'var(--text-secondary)'}}>
        Note: This table only shows 'in_progress' items. Completed items are hidden.
      </p>
    </div>
  );
};

export default ProductionPage;