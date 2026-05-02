import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { monitorApi, type DashboardMetrics } from "@/api/monitor";

const SEVERITY_COLORS: Record<string, string> = {
  success: "#22c55e",
  failure: "#ef4444",
  denied: "#f97316",
};

const MODULE_COLORS = ["#3b82f6", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b"];

export default function MonitorDashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await monitorApi.getDashboard();
      setMetrics(res.data);
    } catch {
      setError("Ошибка загрузки метрик");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Загрузка...</div>;
  if (error) return <div className="p-6 text-red-500">{error}</div>;
  if (!metrics) return null;

  const resultData = Object.entries(metrics.events_by_result).map(([k, v]) => ({ name: k, value: v }));
  const moduleData = Object.entries(metrics.events_by_module).map(([k, v]) => ({ name: k, value: v }));

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Мониторинг</h1>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Событий сегодня" value={metrics.total_events_today} color="blue" />
        <KpiCard label="Неудачных входов" value={metrics.failed_logins_today} color="orange" />
        <KpiCard label="Активных оповещений" value={metrics.active_alerts} color="red" link="/monitor/alerts" />
        <KpiCard label="Критических" value={metrics.critical_alerts} color="red" link="/monitor/alerts?status=new&severity=critical" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-zinc-900 rounded-lg border p-4">
          <h2 className="font-semibold mb-4">События по результату (сегодня)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={resultData}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value">
                {resultData.map((entry, i) => (
                  <Cell key={i} fill={SEVERITY_COLORS[entry.name] || "#94a3b8"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-lg border p-4">
          <h2 className="font-semibold mb-4">События по модулю (сегодня)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={moduleData}>
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value">
                {moduleData.map((_, i) => (
                  <Cell key={i} fill={MODULE_COLORS[i % MODULE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <QuickLink to="/monitor/audit" label="Журнал аудита" desc="Поиск и просмотр событий" />
        <QuickLink to="/monitor/alerts" label="Оповещения" desc="Управление инцидентами" />
        <QuickLink to="/monitor/rules" label="Правила" desc="Настройка правил выявления" />
        <QuickLink to="/monitor/kibana" label="Kibana" desc="Аналитические дашборды" />
      </div>
    </div>
  );
}

function KpiCard({ label, value, color, link }: { label: string; value: number; color: string; link?: string }) {
  const colorMap: Record<string, string> = {
    blue: "text-blue-600",
    orange: "text-orange-500",
    red: "text-red-500",
  };
  const card = (
    <div className="bg-white dark:bg-zinc-900 rounded-lg border p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${colorMap[color] || ""}`}>{value}</p>
    </div>
  );
  return link ? <Link to={link}>{card}</Link> : card;
}

function QuickLink({ to, label, desc }: { to: string; label: string; desc: string }) {
  return (
    <Link
      to={to}
      className="bg-white dark:bg-zinc-900 rounded-lg border p-4 hover:border-blue-500 transition-colors block"
    >
      <p className="font-semibold">{label}</p>
      <p className="text-sm text-muted-foreground mt-1">{desc}</p>
    </Link>
  );
}
