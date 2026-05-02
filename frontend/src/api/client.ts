import axios from "axios";
import { useAuthStore } from "@/store/auth";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const res = await axios.post("/api/auth/refresh", {}, { withCredentials: true });
        const { access_token } = res.data;
        const me = await axios.get("/api/auth/me", {
          headers: { Authorization: `Bearer ${access_token}` },
        });
        useAuthStore.getState().setAuth(access_token, me.data);
        original.headers.Authorization = `Bearer ${access_token}`;
        return api(original);
      } catch {
        useAuthStore.getState().clearAuth();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (username: string, password: string) =>
    api.post<{ access_token: string; token_type: string }>("/auth/login", { username, password }),
  me: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
  refresh: () => api.post("/auth/refresh"),
};

export default api;
