'use client';
import React, { createContext, useContext, useState, useEffect } from 'react';

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

  useEffect(() => {
    try {
      const stored = localStorage.getItem('cw_user');
      if (stored) setUser(JSON.parse(stored));
    } catch {
      // ignore parse errors
    }
  }, []);

  /**
   * Demo-only login: accepts any non-empty credentials and stores them in localStorage.
   * NOTE: This is a frontend simulation — no credentials are validated against a real database.
   * Replace with a real API call once backend authentication is implemented.
   * See BACKEND_CHANGES_REQUIRED.md for full integration details.
   */
  const login = async (username: string, password: string): Promise<boolean> => {
    if (!username || !password) return false;
    // Prefer the previously registered email if the username matches
    let email = username + '@user.local';
    try {
      const existing = localStorage.getItem('cw_user');
      if (existing) {
        const parsed = JSON.parse(existing);
        if (parsed.username === username && parsed.email) {
          email = parsed.email;
        }
      }
    } catch { /* ignore */ }
    const u = { username, email };
    setUser(u);
    localStorage.setItem('cw_user', JSON.stringify(u));
    return true;
  };

  const register = async (username: string, email: string, password: string): Promise<boolean> => {
    if (!username || !email || !password) return false;
    const u = { username, email };
    setUser(u);
    localStorage.setItem('cw_user', JSON.stringify(u));
    return true;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('cw_user');
  };

  return (
    <AuthContext.Provider value={{ user, isLoggedIn: !!user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
