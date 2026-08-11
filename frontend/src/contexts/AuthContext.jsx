import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('access_token'));
  const [loading, setLoading] = useState(true);

  // Fetch current user on mount if token exists
  useEffect(() => {
    if (token) {
      api
        .get('/auth/me')
        .then((res) => {
          setUser(res.data);
        })
        .catch(() => {
          // Token invalid — clear it
          localStorage.removeItem('access_token');
          setToken(null);
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, [token]);

  const login = useCallback(async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token } = res.data;
    localStorage.setItem('access_token', access_token);
    setToken(access_token);
    // Fetch user profile
    const meRes = await api.get('/auth/me', {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    setUser(meRes.data);
    return meRes.data;
  }, []);

  const signup = useCallback(async (email, password, name) => {
    const res = await api.post('/auth/signup', { email, password, name });
    const { access_token } = res.data;
    localStorage.setItem('access_token', access_token);
    setToken(access_token);
    // Fetch user profile
    const meRes = await api.get('/auth/me', {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    setUser(meRes.data);
    return meRes.data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('ci_saved_company_url');
    setToken(null);
    setUser(null);
  }, []);

  const completeOnboarding = useCallback(async (formData) => {
    const res = await api.post('/auth/onboard', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    setUser(res.data);
    return res.data;
  }, []);

  const updateUser = useCallback((updatedUserData) => {
    setUser((prev) => ({ ...prev, ...updatedUserData }));
  }, []);

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!user,
    login,
    signup,
    logout,
    completeOnboarding,
    updateUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
