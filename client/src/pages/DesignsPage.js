// src/pages/DesignsPage.js
import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const DesignsPage = () => {
  const [designs, setDesigns] = useState([]);
  const [clothPurchases, setClothPurchases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { hasAccess } = useAuth();

  // Form state
  const [designCode, setDesignCode] = useState('');
  const [clothId, setClothId] = useState('');
  const [yardsPerPiece, setYardsPerPiece] = useState(1);
  const [numPieces, setNumPieces] = useState(10);
  const [sizeData, setSizeData] = useState('');
  /* Example sizeData:
    S, 2
    M, 3
    L, 3
    XL, 2
  */

  const fetchAllData = async () => {
    setLoading(true);
    setError('');
    try {
      const [designsRes, clothRes] = await Promise.all([
        api.post('/designs/operate', { action: 'READ_ALL' }),
        api.post('/cloth-purchases/operate', { action: 'READ_ALL' })
      ]);
      setDesigns(designsRes.data);
      setClothPurchases(clothRes.data);
      if (clothRes.data.length > 0) {
        setClothId(clothRes.data[0].id); // Default to first cloth
      }
    } catch (err) {
      setError('Failed to fetch data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  const parseSizeData = () => {
    return sizeData.split('\n')
      .filter(line => line.trim() !== '')
      .map(line => {
        const [size, quantity] = line.split(',');
        return {
          size: size.trim(),
          quantity: parseInt(quantity.trim())
        };
      });
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const size_distribution = parseSizeData();
      if (!size_distribution.length) {
        setError("Size distribution is empty or invalid.");
        return;
      }

      await api.post('/designs/operate', {
        action: 'CREATE',
        payload: {
          design_code: designCode,
          cloth_purchase_id: clothId,
          allocated_yards_per_piece: parseFloat(yardsPerPiece),
          number_of_pieces: parseInt(numPieces),
          size_distribution: size_distribution,
        },
      });
      // Reset form
      setDesignCode('');
      setYardsPerPiece(1);
      setNumPieces(10);
      setSizeData('');
      // Refresh list
      fetchAllData();
    } catch (err) {
      setError('Failed to create design. ' + (err.response?.data?.detail || ''));
    }
  };
  
  const handleDelete = async (design_id) => {
    if (!window.confirm('Are you sure? This will return yards to the cloth purchase.')) {
      return;
    }
    setError('');
    try {
      await api.post('/designs/operate', {
        action: 'DELETE',
        design_id: design_id,
      });
      fetchAllData(); // Refresh
    } catch (err) {
      setError('Failed to delete design. ' + (err.response?.data?.detail || ''));
    }
  };

  return (
    <div>
      <h2>Create New Design</h2>
      <form onSubmit={handleCreate} style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
          <div className="form-group">
            <label>Design Code</label>
            <input type="text" value={designCode} onChange={(e) => setDesignCode(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Cloth Purchase</label>
            <select value={clothId} onChange={(e) => setClothId(e.target.value)} required>
              <option value="" disabled>Select Cloth</option>
              {clothPurchases.map(p => (
                <option key={p.id} value={p.id}>{p.cloth_name} ({p.id})</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Yards per Piece</label>
            <input type="number" step="0.1" value={yardsPerPiece} onChange={(e) => setYardsPerPiece(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Number of Pieces</label>
            <input type="number" value={numPieces} onChange={(e) => setNumPieces(e.target.value)} required />
          </div>
          <div className="form-group" style={{flexBasis: '100%'}}>
            <label>Size Distribution (one per line, e.g., "S, 2")</label>
            <textarea
              rows="5"
              value={sizeData}
              onChange={(e) => setSizeData(e.target.value)}
              placeholder="S, 2&#10;M, 3&#10;L, 3&#10;XL, 2"
            />
          </div>
        </div>
        <button type="submit" className="btn btn-primary" style={{marginTop: '10px'}}>Create Design</button>
      </form>
      {error && <p className="error-message">{error}</p>}

      <hr style={{ margin: '20px 0', borderColor: 'var(--border-color)'}} />

      <h2>All Designs</h2>
      {loading ? <p>Loading...</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Design Code</th>
              <th>Cloth ID</th>
              <th>Allocated Yards</th>
              <th>Size Distribution</th>
              {hasAccess(2) && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {designs.map((d) => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td>{d.design_code}</td>
                <td>{d.cloth_purchase_id}</td>
                <td>{d.allocated_yards}</td>
                <td>
                  <pre>{JSON.stringify(d.size_distribution, null, 2)}</pre>
                </td>
                {hasAccess(2) && (
                  <td>
                    <button onClick={() => handleDelete(d.id)} className="btn btn-danger">Delete</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default DesignsPage;