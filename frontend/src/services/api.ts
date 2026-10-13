import axios from "axios";
import { supabase } from "../lib/supabase";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://localhost:8000" : undefined);

if (!apiBaseUrl) {
  throw new Error("VITE_API_URL must be configured for production builds.");
}

const api = axios.create({
  baseURL: apiBaseUrl,
});

api.interceptors.request.use(async (config) => {
  if (supabase) {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (supabase) void supabase.auth.signOut();
    }
    return Promise.reject(error);
  },
);

export default api;
