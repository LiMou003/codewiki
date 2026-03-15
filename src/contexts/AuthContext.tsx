'use client';
import React, { createContext, useContext, useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';

// Add '; Secure' only when running over HTTPS (i.e. in production)
const COOKIE_FLAGS =
  typeof window !== 'undefined' && window.location.protocol === 'https:'
    ? 'path=/; SameSite=Lax; Secure'
    : 'path=/; SameSite=Lax';

interface User {
  username: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  isLoggedIn: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  register: (username: string, email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoggedIn: false,
  login: async () => false,
  register: async () => false,
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  // On mount: restore user from localStorage and verify the stored token
  useEffect(() => {
    const stored = localStorage.getItem('cw_user');
    const token = localStorage.getItem('cw_token');
    if (stored && token) {
      try {
        setUser(JSON.parse(stored));
        // Ensure the middleware cookie is set in case it was cleared
        document.cookie = `cw_authed=1; ${COOKIE_FLAGS}`;
      } catch {
        // ignore parse errors
      }
      // Verify token is still valid in background
      fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          if (!res.ok) {
            // Token expired or invalid — clear session
            localStorage.removeItem('cw_user');
            localStorage.removeItem('cw_token');
            document.cookie = `cw_authed=; ${COOKIE_FLAGS}; max-age=0`;
            setUser(null);
          }
        })
        .catch(() => {
          // Backend unreachable — keep session for offline UX
        });
    }
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    if (!username || !password) return false;
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      const u: User = { username: data.user.username, email: data.user.email };
      setUser(u);
      localStorage.setItem('cw_user', JSON.stringify(u));
      localStorage.setItem('cw_token', data.access_token);
      // Cookie lets Next.js middleware detect authentication server-side
      document.cookie = `cw_authed=1; ${COOKIE_FLAGS}`;
      return true;
    } catch {
      return false;
    }
  };

  const register = async (
    username: string,
    email: string,
    password: string
  ): Promise<boolean> => {
    if (!username || !email || !password) return false;
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      const u: User = { username: data.user.username, email: data.user.email };
      setUser(u);
      localStorage.setItem('cw_user', JSON.stringify(u));
      localStorage.setItem('cw_token', data.access_token);
      // Cookie lets Next.js middleware detect authentication server-side
      document.cookie = `cw_authed=1; ${COOKIE_FLAGS}`;
      return true;
    } catch {
      return false;
    }
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('cw_user');
    localStorage.removeItem('cw_token');
    // Remove the middleware session cookie
    document.cookie = `cw_authed=; ${COOKIE_FLAGS}; max-age=0`;
  };

  return (
    <AuthContext.Provider value={{ user, isLoggedIn: !!user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
