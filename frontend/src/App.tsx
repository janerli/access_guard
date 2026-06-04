import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Users from "@/pages/identity/Users";
import UserDetail from "@/pages/identity/UserDetail";
import Structure from "@/pages/identity/Structure";
import Events from "@/pages/identity/Events";
import Roles from "@/pages/access/Roles";
import RoleDetail from "@/pages/access/RoleDetail";
import Matrix from "@/pages/access/Matrix";
import Requests from "@/pages/access/Requests";
import MonitorDashboard from "@/pages/monitor/Dashboard";
import AuditLog from "@/pages/monitor/AuditLog";
import Alerts from "@/pages/monitor/Alerts";
import Rules from "@/pages/monitor/Rules";
import KibanaPage from "@/pages/monitor/Kibana";
import ThreatSimulator from "@/pages/monitor/ThreatSimulator";
import ReportTemplates from "@/pages/reports/Templates";
import NewReport from "@/pages/reports/NewReport";
import ReportHistory from "@/pages/reports/History";
import ReportSchedules from "@/pages/reports/Schedules";
import PreviewReport from "@/pages/reports/PreviewReport";
import AuditEventDetail from "@/pages/monitor/AuditEventDetail";
import Profile from "@/pages/Profile";
import RoleGraph from "@/pages/access/RoleGraph";
import UserAccessDetail from "@/pages/access/UserAccessDetail";
import SystemHealth from "@/pages/monitor/SystemHealth";

function RequireAuth({ children }: { children: ReactNode }) {
  const { token } = useAuthStore();
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-slate-800">{title}</h1>
      <p className="text-slate-500 mt-2">Модуль в разработке</p>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<Dashboard />} />

          {/* Identity module */}
          <Route path="/identity" element={<Navigate to="/identity/users" replace />} />
          <Route path="/identity/users" element={<Users />} />
          <Route path="/identity/users/:id" element={<UserDetail />} />
          <Route path="/access/users/:id" element={<UserAccessDetail />} />
          <Route path="/identity/structure" element={<Structure />} />
          <Route path="/identity/events" element={<Events />} />

          {/* Profile */}
          <Route path="/profile" element={<Profile />} />

          {/* Access module */}
          <Route path="/access" element={<Navigate to="/access/roles" replace />} />
          <Route path="/access/roles" element={<Roles />} />
          <Route path="/access/roles/:id" element={<RoleDetail />} />
          <Route path="/access/matrix" element={<Matrix />} />
          <Route path="/access/requests" element={<Requests />} />
          <Route path="/access/graph" element={<RoleGraph />} />

          {/* Monitor module */}
          <Route path="/monitor" element={<Navigate to="/monitor/dashboard" replace />} />
          <Route path="/monitor/dashboard" element={<MonitorDashboard />} />
          <Route path="/monitor/audit" element={<AuditLog />} />
          <Route path="/monitor/alerts" element={<Alerts />} />
          <Route path="/monitor/rules" element={<Rules />} />
          <Route path="/monitor/kibana" element={<KibanaPage />} />
          <Route path="/monitor/simulator" element={<ThreatSimulator />} />
          <Route path="/monitor/health" element={<SystemHealth />} />

          {/* Reports module */}
          <Route path="/reports" element={<Navigate to="/reports/templates" replace />} />
          <Route path="/reports/templates" element={<ReportTemplates />} />
          <Route path="/reports/new/:templateCode" element={<NewReport />} />
          <Route path="/reports/history" element={<ReportHistory />} />
          <Route path="/reports/schedules" element={<ReportSchedules />} />
          <Route path="/reports/preview/:id" element={<PreviewReport />} />

          {/* Audit event detail */}
          <Route path="/monitor/audit/:event_id" element={<AuditEventDetail />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
