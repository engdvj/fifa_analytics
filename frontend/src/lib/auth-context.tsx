"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { auth, type User } from "./api";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string) => Promise<User>;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("auth_token");
    if (!stored) {
      setIsLoading(false);
      return;
    }
    auth
      .me(stored)
      .then((u) => {
        setToken(stored);
        setUser(u);
      })
      .catch(() => {
        localStorage.removeItem("auth_token");
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = async (newToken: string): Promise<User> => {
    localStorage.setItem("auth_token", newToken);
    const u = await auth.me(newToken);
    setToken(newToken);
    setUser(u);
    return u;
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    setToken(null);
    setUser(null);
  };

  const refresh = async () => {
    const t = token ?? localStorage.getItem("auth_token");
    if (!t) return;
    try {
      setUser(await auth.me(t));
    } catch {
      /* mantém o user atual se a atualização falhar */
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        refresh,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
