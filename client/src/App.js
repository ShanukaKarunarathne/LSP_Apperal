// src/App.js
import React from 'react';
import { Routes, Route } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import Dashboard from './pages/Dashboard';
import ClothPurchasesPage from './pages/ClothPurchasesPage';
import DesignsPage from './pages/DesignsPage';
import ProductionPage from './pages/ProductionPage';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      
      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="cloth-purchases" element={<ClothPurchasesPage />} />
        <Route path="designs" element={<DesignsPage />} />
        <Route path="production" element={<ProductionPage />} />
      </Route>
    </Routes>
  );
}

export default App;