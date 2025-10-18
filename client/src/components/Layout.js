// src/components/Layout.js
import React from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

const Layout = () => {
  const { logout, user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      <header className="header">
        <nav>
          <Link to="/">Dashboard</Link>
          <Link to="/cloth-purchases">Cloth</Link>
          <Link to="/designs">Designs</Link>
          <Link to="/production">Production</Link>
        </nav>
        <div className="header-controls">
          <span>Hi, {user?.username} ({user?.access_level})</span>
          <button onClick={toggleTheme} className="btn btn-secondary">
            {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
          </button>
          <button onClick={handleLogout} className="btn btn-danger">
            Logout
          </button>
        </div>
      </header>
      <main className="app-container">
        <Outlet />
      </main>
    </>
  );
};

export default Layout;