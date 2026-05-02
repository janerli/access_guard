import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: "system_admin" | "security_officer" | "hr_operator" | "auditor";
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  token: string | null;
  user: AdminUser | null;
  setAuth: (token: string, user: AdminUser) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      clearAuth: () => set({ token: null, user: null }),
    }),
    {
      name: "accessguard-auth",
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);
