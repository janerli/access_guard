import { api } from "./client";

export type ReportDataSource = "postgres" | "elasticsearch" | "combined";
export type ReportFormat = "pdf" | "xlsx" | "csv";
export type ReportStatus = "pending" | "generating" | "ready" | "failed";

export interface ReportTemplate {
  id: string;
  code: string;
  name: string;
  description: string;
  data_source: ReportDataSource;
  parameters_schema: Record<string, unknown>;
  output_formats: ReportFormat[];
}

export interface Report {
  id: string;
  template_id: string;
  requested_by: string | null;
  parameters: Record<string, unknown>;
  format: ReportFormat;
  status: ReportStatus;
  created_at: string;
  completed_at: string | null;
  file_path: string | null;
  file_size: number | null;
  error_message: string | null;
  template?: ReportTemplate;
}

export interface ReportsListResponse {
  items: Report[];
  total: number;
  page: number;
  page_size: number;
}

export interface ReportSchedule {
  id: string;
  template_id: string;
  parameters: Record<string, unknown>;
  format: ReportFormat;
  cron_expression: string;
  delivery_channel_id: string | null;
  is_enabled: boolean;
  last_run_at: string | null;
  template?: ReportTemplate;
}

export const reportsApi = {
  listTemplates: () => api.get<ReportTemplate[]>("/reports/templates"),

  getTemplate: (code: string) => api.get<ReportTemplate>(`/reports/templates/${code}`),

  createReport: (body: { template_code: string; parameters: Record<string, unknown>; format: ReportFormat }) =>
    api.post<Report>("/reports/", body),

  listReports: (params?: { template_code?: string; status?: string; page?: number; page_size?: number }) =>
    api.get<ReportsListResponse>("/reports/", { params }),

  getReport: (id: string) => api.get<Report>(`/reports/${id}`),

  downloadReport: (id: string) =>
    api.get(`/reports/${id}/download`, { responseType: "blob" }),

  listSchedules: () => api.get<ReportSchedule[]>("/reports/schedules/"),

  createSchedule: (body: {
    template_code: string;
    parameters: Record<string, unknown>;
    format: ReportFormat;
    cron_expression: string;
    is_enabled: boolean;
  }) => api.post<ReportSchedule>("/reports/schedules/", body),

  updateSchedule: (id: string, body: Partial<ReportSchedule>) =>
    api.patch<ReportSchedule>(`/reports/schedules/${id}`, body),

  deleteSchedule: (id: string) => api.delete(`/reports/schedules/${id}`),

  runScheduleNow: (id: string) =>
    api.post<Report>(`/reports/schedules/${id}/run`),
};
