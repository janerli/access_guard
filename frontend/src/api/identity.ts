import { api } from "./client";

export type UserStatus = "new" | "active" | "suspended" | "blocked" | "deleted";

export interface Position {
  id: string;
  code: string;
  name: string;
  level: number;
}

export interface Department {
  id: string;
  code: string;
  name: string;
  parent_id?: string;
  manager_user_id?: string;
}

export interface User {
  id: string;
  employee_id: string;
  username: string;
  email: string;
  full_name: string;
  status: UserStatus;
  position_id?: string;
  department_id?: string;
  position?: Position;
  department?: Department;
  ldap_dn?: string;
  created_at: string;
  updated_at: string;
}

export interface UsersListResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
}

export interface LifecycleEvent {
  id: string;
  user_id?: string;
  event_type: string;
  source: string;
  status: string;
  processed_at?: string;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface LifecycleEventsResponse {
  items: LifecycleEvent[];
  total: number;
}

export interface UserCreateBody {
  employee_id: string;
  username: string;
  email: string;
  full_name: string;
  position_code?: string;
  department_code?: string;
}

export interface UserUpdateBody {
  email?: string;
  full_name?: string;
  position_code?: string;
  department_code?: string;
}

export const identityApi = {
  listUsers: (params: {
    status?: string;
    search?: string;
    department_id?: string;
    page?: number;
    page_size?: number;
  }) => api.get<UsersListResponse>("/identity/users", { params }),

  getUser: (id: string) => api.get<User>(`/identity/users/${id}`),

  createUser: (body: UserCreateBody) => api.post<User>("/identity/users", body),

  updateUser: (id: string, body: UserUpdateBody) =>
    api.patch<User>(`/identity/users/${id}`, body),

  suspendUser: (id: string) => api.post<User>(`/identity/users/${id}/suspend`),
  restoreUser: (id: string) => api.post<User>(`/identity/users/${id}/restore`),
  blockUser: (id: string) => api.post<User>(`/identity/users/${id}/block`),
  deleteUser: (id: string) => api.delete(`/identity/users/${id}`),

  resetPassword: (id: string, new_password: string) =>
    api.post(`/identity/users/${id}/reset-password`, { new_password }),

  listPositions: () => api.get<Position[]>("/identity/positions"),
  listDepartments: () => api.get<Department[]>("/identity/departments"),

  listEvents: (params: { user_id?: string; event_type?: string; page?: number }) =>
    api.get<LifecycleEventsResponse>("/identity/events", { params }),
};
