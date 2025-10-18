// src/pages/ClothPurchasesPage.js
import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const ClothPurchasesPage = () => {
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { hasAccess } = useAuth();

  // Form state
  const [clothName, setClothName] = useState('');
  const [supplierName, setSupplierName] = useState('');
  const [totalYards, setTotalYards] = useState(0);
  const [numRolls, setNumRolls] = useState(0);
  const [numColors, setNumColors] = useState(0);

  const fetchPurchases = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.post('/cloth-purchases/operate', {
        action: 'READ_ALL',
      });
      setPurchases(response.data);
    } catch (err) {
      setError('Failed to fetch cloth purchases.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPurchases();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.post('/cloth-purchases/operate', {
        action: 'CREATE',
        payload: {
          cloth_name: clothName,
          supplier_name: supplierName,
          total_yards: parseInt(totalYards),
          number_of_rolls: parseInt(numRolls),
          number_of_colors: parseInt(numColors),
        },
      });
      // Reset form
      setClothName('');
      setSupplierName('');
      setTotalYards(0);
      setNumRolls(0);
      setNumColors(0);
      // Refresh list
      fetchPurchases();
    } catch (err) {
      setError('Failed to create purchase. ' + (err.response?.data?.detail || ''));
    }
  };
  
  const handleDelete = async (purchase_id) => {
    if (!window.confirm('Are you sure you want to delete this purchase?')) {
      return;
    }
    setError('');
    try {
      await api.post('/cloth-purchases/operate', {
        action: 'DELETE',
        purchase_id: purchase_id,
      });
      fetchPurchases(); // Refresh
    } catch (err) {
      setError('Failed to delete purchase. ' + (err.response?.data?.detail || ''));
    }
  };

  return (
    <div>
      <h2>Create New Cloth Purchase</h2>
      <form onSubmit={handleCreate} style={{ display: 'flex', flexWrap: 'wrap', gap: '15px', marginBottom: '20px' }}>
        <div className="form-group">
          <label>Cloth Name</label>
          <input type="text" value={clothName} onChange={(e) => setClothName(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Supplier Name</label>
          <input type="text" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Total Yards</label>
          <input type="number" value={totalYards} onChange={(e) => setTotalYards(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Number of Rolls</label>
          <input type="number" value={numRolls} onChange={(e) => setNumRolls(e.target.value)} required />
        </div>
        <div className="form-group">
          <label>Number of Colors</label>
          <input type="number" value={numColors} onChange={(e) => setNumColors(e.target.value)} required />
        </div>
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <button type="submit" className="btn btn-primary">Create Purchase</button>
        </div>
      </form>
      {error && <p className="error-message">{error}</p>}

      <hr style={{ margin: '20px 0', borderColor: 'var(--border-color)'}} />

      <h2>All Cloth Purchases</h2>
      {loading ? <p>Loading...</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Cloth Name</th>
              <th>Supplier</th>
              <th>Total Yards</th>
              <th>Rolls</th>
              <th>Colors</th>
              <th>Created At</th>
              {hasAccess(2) && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {purchases.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>{p.cloth_name}</td>
                <td>{p.supplier_name}</td>
                <td>{p.total_yards}</td>
                <td>{p.number_of_rolls}</td>
                <td>{p.number_of_colors}</td>
                <td>{new Date(p.created_at).toLocaleString()}</td>
                {hasAccess(2) && (
                  <td>
                    {/* Update is more complex, so we just include Delete for simplicity */}
                    <button onClick={() => handleDelete(p.id)} className="btn btn-danger">Delete</button>
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

export default ClothPurchasesPage;