import { useEffect, useState, type ReactNode } from "react";
import api from "../services/api";
import type { AuthResponse, User } from "../types/auth";

import { AuthContext } from "./authContextValue";

function storedUser(): User | null {
  const value = localStorage.getItem("current_user");
  if (!value) return null;
  try {
    return JSON.parse(value) as User;
  } catch {
    localStorage.removeItem("current_user");
    localStorage.removeItem("access_token");
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(storedUser);

  useEffect(() => {
    const clearSession = () => setUser(null);
    window.addEventListener("auth:logout", clearSession);
    return () => window.removeEventListener("auth:logout", clearSession);
  }, []);

  const saveSession = (response: AuthResponse) => {
    localStorage.setItem("access_token", response.access_token);
    localStorage.setItem("current_user", JSON.stringify(response.user));
    setUser(response.user);
  };

  const login = async (email: string, password: string) => {
    const { data } = await api.post<AuthResponse>("/api/auth/login", { email, password });
    saveSession(data);
  };

  const register = async (name: string, email: string, password: string) => {
    await api.post("/api/auth/register", { name, email, password });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("current_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, isLoading: false, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

