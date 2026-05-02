import { api } from "./client";

export type AuditTargetType = "user" | "role" | "resource" | "system";
export type AuditOperation =
  | "create" | "read" | "update" | "delete"
  | "login_success" | "login_failure" | "permission_check"
  | "role_assign" | "role_revoke" | "password_reset"
  | "suspend" | "restore" | "block"
  | "request_submit" | "request_approve" | "request_reject" | "request_withdraw";
export type AuditModule = "identity" | "access" | "monitor" | "reports" | "auth";
export type AuditResult = "success" | "failure" | "denied";
export type AlertSeverity = "info" | "low" | "medium" | "high" | "critical";
export type AlertStatus = "new" | "acknowledged" | "resolved" | "false_positive";
export type AlertDataSource = "postgres" | "elasticsearch";
export type AlertConditionType = "threshold" | "pattern" | "anomaly";
export type NotificationChannelType = "email" | "webhook" | "log" | "kafka";

export interface AuditLogEntry {
  id: number;
  event_id: string;
  timestamp: string;
  actor_id: string | null;
  actor_username: string;
  target_type: AuditTargetType;
  target_id: string;
  operation: AuditOperation;
  module: AuditModule;
  result: AuditResult;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown> | null;
  correlation_id: string | null;
  published_to_kafka: boolean;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AlertRule {
  id: string;
  code: string;
  name: string;
  description: string;
  condition_type: AlertConditionType;
  condition_config: Record<string, unknown>;
  severity: AlertSeverity;
  is_enabled: boolean;
  cooldown_seconds: number;
  data_source: AlertDataSource;
}

export interface AlertRulesListResponse {
  items: AlertRule[];
  total: number;
}

export interface Alert {
  id: string;
  rule_id: string;
  triggered_at: string;
  subject_user_id: string | null;
  severity: AlertSeverity;
  status: AlertStatus;
  correlation_id: string | null;
  details: Record<string, unknown>;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolution_comment: string | null;
  rule?: AlertRule;
}

export interface AlertsListResponse {
  items: Alert[];
  total: number;
  page: number;
  page_size: number;
}

export interface NotificationChannel {
  id: string;
  code: string;
  type: NotificationChannelType;
  config: Record<string, unknown>;
  is_enabled: boolean;
}

export interface DashboardMetrics {
  total_events_today: number;
  failed_logins_today: number;
  active_alerts: number;
  critical_alerts: number;
  events_by_module: Record<string, number>;
  events_by_result: Record<string, number>;
}

export const monitorApi = {
  getDashboard: () => api.get<DashboardMetrics>("/monitor/dashboard"),

  listAudit: (params: {
    actor_username?: string;
    operation?: string;
    module?: string;
    result?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) => api.get<AuditLogListResponse>("/monitor/audit", { params }),

  getAuditEntry: (event_id: string) =>
    api.get<AuditLogEntry>(`/monitor/audit/${event_id}`),

  exportAudit: (params: { date_from?: string; date_to?: string; fmt?: string }) =>
    api.get("/monitor/audit/export", { params, responseType: "blob" }),

  listRules: () => api.get<AlertRulesListResponse>("/monitor/rules"),

  createRule: (body: Omit<AlertRule, "id">) =>
    api.post<AlertRule>("/monitor/rules", body),

  updateRule: (id: string, body: Partial<AlertRule>) =>
    api.patch<AlertRule>(`/monitor/rules/${id}`, body),

  toggleRule: (id: string) =>
    api.post<AlertRule>(`/monitor/rules/${id}/toggle`),

  testRule: (id: string) =>
    api.post<{ rule_code: string; matched: boolean; details: Record<string, unknown> }>(
      `/monitor/rules/${id}/test`
    ),

  listAlerts: (params: {
    status?: string;
    severity?: string;
    page?: number;
    page_size?: number;
  }) => api.get<AlertsListResponse>("/monitor/alerts", { params }),

  getAlert: (id: string) => api.get<Alert>(`/monitor/alerts/${id}`),

  acknowledgeAlert: (id: string, comment?: string) =>
    api.post<Alert>(`/monitor/alerts/${id}/acknowledge`, { comment }),

  resolveAlert: (id: string, comment?: string) =>
    api.post<Alert>(`/monitor/alerts/${id}/resolve`, { comment }),

  markFalsePositive: (id: string, comment?: string) =>
    api.post<Alert>(`/monitor/alerts/${id}/false-positive`, { comment }),

  listChannels: () => api.get<NotificationChannel[]>("/monitor/channels"),

  createChannel: (body: Omit<NotificationChannel, "id">) =>
    api.post<NotificationChannel>("/monitor/channels", body),

  updateChannel: (id: string, body: { config?: Record<string, unknown>; is_enabled?: boolean }) =>
    api.patch<NotificationChannel>(`/monitor/channels/${id}`, body),

  getKibanaToken: () =>
    api.get<{ embed_url: string; token: string | null }>("/monitor/kibana-token"),
};
