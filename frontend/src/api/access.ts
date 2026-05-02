import { api } from "./client";

export type AccessRequestStatus = "pending" | "approved" | "rejected" | "withdrawn";
export type ResourceType = "file_share" | "application" | "database" | "api";

export interface Permission {
  id: string;
  code: string;
  description: string;
}

export interface Role {
  id: string;
  code: string;
  name: string;
  description: string;
  is_privileged: boolean;
  owner_user_id?: string;
}

export interface RoleDetail extends Role {
  permissions: Permission[];
}

export interface RolesListResponse {
  items: Role[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserRole {
  id: string;
  user_id: string;
  role_id: string;
  role: Role;
  granted_at: string;
  granted_by?: string;
  expires_at?: string;
  request_id?: string;
}

export interface AccessRequest {
  id: string;
  user_id: string;
  role_id: string;
  role: Role;
  justification: string;
  status: AccessRequestStatus;
  created_at: string;
  decided_at?: string;
  decided_by?: string;
  decision_comment?: string;
}

export interface AccessRequestsListResponse {
  items: AccessRequest[];
  total: number;
  page: number;
  page_size: number;
}

export interface PositionMatrixRow {
  position_id: string;
  position_code: string;
  position_name: string;
  role_ids: string[];
  roles: Role[];
}

export const accessApi = {
  // Permissions
  listPermissions: () => api.get<Permission[]>("/access/permissions"),

  // Roles
  listRoles: (params?: { search?: string; page?: number; page_size?: number }) =>
    api.get<RolesListResponse>("/access/roles", { params }),

  getRole: (id: string) => api.get<RoleDetail>(`/access/roles/${id}`),

  createRole: (body: { code: string; name: string; description?: string; is_privileged?: boolean }) =>
    api.post<Role>("/access/roles", body),

  updateRole: (id: string, body: { name?: string; description?: string; is_privileged?: boolean }) =>
    api.patch<Role>(`/access/roles/${id}`, body),

  deleteRole: (id: string) => api.delete(`/access/roles/${id}`),

  addPermissionToRole: (roleId: string, permissionId: string) =>
    api.post(`/access/roles/${roleId}/permissions/${permissionId}`),

  removePermissionFromRole: (roleId: string, permissionId: string) =>
    api.delete(`/access/roles/${roleId}/permissions/${permissionId}`),

  // User roles
  getUserRoles: (userId: string) => api.get<UserRole[]>(`/access/users/${userId}/roles`),

  assignRole: (userId: string, body: { role_id: string; expires_at?: string }) =>
    api.post<UserRole>(`/access/users/${userId}/roles`, body),

  revokeRole: (userId: string, userRoleId: string) =>
    api.delete(`/access/users/${userId}/roles/${userRoleId}`),

  // Permission check
  checkPermission: (userId: string, permissionCode: string) =>
    api.post<{ user_id: string; permission_code: string; allowed: boolean }>("/access/check", {
      user_id: userId,
      permission_code: permissionCode,
    }),

  // Access requests
  listRequests: (params?: { user_id?: string; status?: string; page?: number; page_size?: number }) =>
    api.get<AccessRequestsListResponse>("/access/requests", { params }),

  getRequest: (id: string) => api.get<AccessRequest>(`/access/requests/${id}`),

  createRequest: (body: { user_id: string; role_id: string; justification: string }) =>
    api.post<AccessRequest>("/access/requests", body),

  approveRequest: (id: string, comment?: string) =>
    api.post<AccessRequest>(`/access/requests/${id}/approve`, { comment }),

  rejectRequest: (id: string, comment?: string) =>
    api.post<AccessRequest>(`/access/requests/${id}/reject`, { comment }),

  withdrawRequest: (id: string) => api.delete(`/access/requests/${id}`),

  // Matrix
  getMatrix: () => api.get<PositionMatrixRow[]>("/access/matrix"),

  updateMatrix: (positionId: string, roleIds: string[]) =>
    api.patch("/access/matrix", { position_id: positionId, role_ids: roleIds }),
};
