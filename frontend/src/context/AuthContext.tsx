import { useEffect, useState, type ReactNode } from "react";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import api from "../services/api";
import { supabase } from "../lib/supabase";
import type { User } from "../types/auth";
import { AuthContext } from "./authContextValue";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!supabase) {
      setIsLoading(false);
      return;
    }

    let mounted = true;
    let authRevision = 0;
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event: AuthChangeEvent, session: Session | null) => {
        const revision = ++authRevision;
        if (!session) {
          if (mounted) {
            setUser(null);
            setIsLoading(false);
          }
          return;
        }

        if (mounted) {
          setIsLoading(true);
        }

        window.setTimeout(() => {
          void api.get<User>("/api/auth/me").then(({ data }) => {
            if (mounted && revision === authRevision) setUser(data);
          }).catch(() => {
            if (mounted && revision === authRevision) setUser(null);
          }).finally(() => {
            if (mounted && revision === authRevision) setIsLoading(false);
          });
        }, 0);
      },
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const loadProfile = async (): Promise<void> => {
    const { data } = await api.get<User>("/api/auth/me");
    setUser(data);
  };

  const login = async (email: string, password: string) => {
    if (!supabase) throw new Error("Supabase is not configured.");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    try {
      await loadProfile();
    } catch (error) {
      await supabase.auth.signOut();
      throw error;
    }
  };

  const register = async (name: string, email: string, password: string): Promise<boolean> => {
    if (!supabase) throw new Error("Supabase is not configured.");
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { display_name: name.trim() } },
    });
    if (error) throw error;
    if (!data.session) return false;
    try {
      await loadProfile();
      return true;
    } catch (error) {
      await supabase.auth.signOut();
      throw error;
    }
  };

  const logout = async () => {
    try {
      if (supabase) {
        const { error } = await supabase.auth.signOut();
        if (error) throw error;
      }
    } finally {
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

