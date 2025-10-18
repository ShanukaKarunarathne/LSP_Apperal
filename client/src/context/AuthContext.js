// src/context/AuthContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('token'));

  useEffect(() => {
    if (token) {
      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
      // Set token for all future API requests
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    }
  }, [token]);

  const login = (userData, accessToken) => {
    const { access_level, username } = userData;
    const userToStore = { username, access_level };

    localStorage.setItem('token', accessToken);
    localStorage.setItem('user', JSON.stringify(userToStore));
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;

    setToken(accessToken);
    setUser(userToStore);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    delete api.defaults.headers.common['Authorization'];
    setToken(null);
    setUser(null);
  };

  const hasAccess = (level) => {
    if (!user) return false;
    if (level === 1) {
      return ['read_write', 'full_access'].includes(user.access_level);
    }
    if (level === 2) {
      return user.access_level === 'full_access';
    }
    return false;
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, hasAccess }}>
      {children}
    </AuthContext.Provider>
  );
};