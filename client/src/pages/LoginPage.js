// src/pages/LoginPage.js
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';

const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const auth = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // The API expects form-data for login
    const params = new URLSearchParams();
    params.append('username', username);
    params.append('password', password);

    try {
      const response = await api.post('/users/token', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });
      
//... inside handleSubmit
      // The username is in our state, and the response has the rest
      const { access_token, access_level } = response.data;

      // Manually create the user object to pass to the context
      const userToLogin = {
        username: username, // Get username from component state
        access_level: access_level // Get access_level from API response
      };

      auth.login(userToLogin, access_token);
      navigate('/');
    } catch (err) {
//...
      setError('Failed to login. Please check your credentials.');
      console.error(err);
    }
  };

  return (
    <div className="form-container">
      <h2>LSP Apparel Login</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>
          Login
        </button>
      </form>
      <p style={{ marginTop: '15px', textAlign: 'center' }}>
        No account? <Link to="/register">Register here</Link>
      </p>
    </div>
  );
};

export default LoginPage;