import { useEffect, useState, useCallback } from "react";
import { monitorApi, type HealthResponse, type ServiceStatus } from "@/api/monitor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function StatusIcon({ status }: { status: string }) {
  if (status === "ok") return <span className="text-green-500 text-lg font-bold">OK</span>;
  if (status === "degraded") return <span className="text-yellow-500 text-lg font-bold">!</span>;
  return <span className="text-red-500 text-lg font-bold">ERR</span>;
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "ok"
      ? "bg-green-100 text-green-800"
      : status === "degraded"
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {status.toUpperCase()}
    </span>
  );
}

function ServiceCard({
  name,
  svc,
}: {
  name: string;
  svc: ServiceStatus;
}) {
  return (
    <Card className={`border-l-4 ${svc.status === "ok" ? "border-l-green-500" : svc.status === "degraded" ? "border-l-yellow-500" : "border-l-red-500"}`}>
      <CardContent className="py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusIcon status={svc.status} />
          <div>
            <p className="font-medium text-slate-800">{name}</p>
            {svc.latency_ms !== undefined && (
              <p className="text-xs text-slate-500">{svc.latency_ms} мс</p>
            )}
          </div>
        </div>
        <StatusBadge status={svc.status} />
      </CardContent>
    </Card>
  );
}

export default function SystemHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await monitorApi.getHealth();
      setHealth(res.data);
      setLastCheck(new Date());
      setError("");
    } catch {
      setError("Не удалось получить данные о состоянии системы");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => { void load(); }, 30000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Состояние системы</h1>
        <div className="text-xs text-slate-500 text-right">
          <p>Авто-обновление: каждые 30 сек</p>
          {lastCheck && <p>Последняя проверка: {lastCheck.toLocaleTimeString("ru")}</p>}
          <button onClick={load} className="text-blue-600 hover:underline mt-1">Обновить</button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>
      )}

      {loading && !health && (
        <p className="text-slate-500">Загрузка...</p>
      )}

      {health && (
        <>
          {/* Services */}
          <div>
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-3">Сервисы</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <ServiceCard name="PostgreSQL" svc={health.postgres} />
              <ServiceCard name="Redis" svc={health.redis} />
              <ServiceCard name="Elasticsearch" svc={health.elasticsearch} />
              <ServiceCard name="Kafka" svc={health.kafka} />
            </div>
          </div>

          {/* Outbox + Celery */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Transactional Outbox</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">В ожидании</span>
                  <span className={`font-semibold ${health.outbox_pending > 10 ? "text-yellow-600" : "text-green-600"}`}>
                    {health.outbox_pending}
                    {health.outbox_pending > 10 && " !"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">С ошибкой</span>
                  <span className={`font-semibold ${health.outbox_failed > 0 ? "text-red-600" : "text-green-600"}`}>
                    {health.outbox_failed}
                    {health.outbox_failed > 0 && " err"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 pt-1">
                  0 в ожидании — норма: publisher обрабатывает каждые 10 сек
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Celery</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Задач в Redis</span>
                  <span className="font-semibold text-slate-800">{health.celery_tasks_in_redis}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-600">Beat последний запуск</span>
                  <span className="text-slate-600 font-mono text-xs">
                    {health.last_celery_beat
                      ? new Date(health.last_celery_beat).toLocaleTimeString("ru")
                      : "не зафиксирован"}
                  </span>
                </div>
                <p className="text-xs text-slate-400 pt-1">
                  Beat пишет ключ <code>celery_beat_last_run</code> в Redis
                </p>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
