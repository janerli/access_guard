import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "@/api/client";

interface AuditEvent {
  id: number;
  event_id: string;
  timestamp: string;
  actor_id: string | null;
  actor_username: string | null;
  target_type: string;
  target_id: string | null;
  operation: string;
  module: string;
  result: string;
  ip_address: string | null;
  user_agent: string | null;
  details: Record<string, unknown>;
  correlation_id: string | null;
  published_to_kafka: boolean;
}

interface CorrelationEvent {
  event_id: string | null;
  timestamp: string | null;
  actor_username: string | null;
  module: string | null;
  operation: string | null;
  result: string | null;
  target_type: string | null;
  target_id: string | null;
  correlation_id: string | null;
  source: "elasticsearch" | "postgresql";
}

interface CorrelationChain {
  correlation_id: string | null;
  events: CorrelationEvent[];
  total: number;
}

const MODULE_COLORS: Record<string, string> = {
  identity: "bg-blue-100 text-blue-700",
  access: "bg-purple-100 text-purple-700",
  monitor: "bg-orange-100 text-orange-700",
  reports: "bg-green-100 text-green-700",
  system: "bg-slate-100 text-slate-700",
};

const RESULT_COLORS: Record<string, string> = {
  success: "text-green-600",
  failure: "text-red-600",
  partial: "text-yellow-600",
  denied: "text-red-700",
};

const RESULT_ICONS: Record<string, string> = {
  success: "✓",
  failure: "✗",
  partial: "~",
  denied: "⊘",
};

function formatTs(ts: string | null): string {
  if (!ts) return "—";
  return new Date(ts).toLocaleString("ru", { dateStyle: "short", timeStyle: "medium" });
}

export default function AuditEventDetail() {
  const { event_id } = useParams<{ event_id: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<AuditEvent | null>(null);
  const [chain, setChain] = useState<CorrelationChain | null>(null);
  const [loading, setLoading] = useState(true);
  const [chainLoading, setChainLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!event_id) return;
    setLoading(true);
    api.get<AuditEvent>(`/monitor/audit/${event_id}`)
      .then(r => {
        setEvent(r.data);
        // Load correlation chain
        if (r.data.correlation_id) {
          setChainLoading(true);
          api.get<CorrelationChain>(`/monitor/audit/${event_id}/correlation`)
            .then(c => setChain(c.data))
            .catch(() => { /* chain unavailable */ })
            .finally(() => setChainLoading(false));
        }
      })
      .catch(() => setError("Событие не найдено"))
      .finally(() => setLoading(false));
  }, [event_id]);

  const openKibana = () => {
    if (!event?.correlation_id) return;
    const base = "http://localhost:5601";
    const query = encodeURIComponent(`correlation_id:"${event.correlation_id}"`);
    window.open(`${base}/app/discover#/?_g=()&_a=(query:(language:kuery,query:'${query}'))`, "_blank");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error || !event) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500 text-lg">{error || "Событие не найдено"}</p>
        <button onClick={() => navigate("/monitor/audit")}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          ← К журналу аудита
        </button>
      </div>
    );
  }

  const detailEntries = Object.entries(event.details || {});

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button
            onClick={() => navigate("/monitor/audit")}
            className="text-sm text-slate-500 hover:text-slate-800 flex items-center gap-1 mb-2"
          >
            ← Журнал аудита
          </button>
          <h1 className="text-xl font-bold text-slate-900">
            Событие: <span className="font-mono text-blue-700">{event.operation}</span>
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">{formatTs(event.timestamp)}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${RESULT_COLORS[event.result] || "text-slate-600"}`}>
            {RESULT_ICONS[event.result]} {event.result}
          </span>
          <span className={`text-xs px-2 py-1 rounded font-medium ${MODULE_COLORS[event.module] || "bg-slate-100 text-slate-700"}`}>
            {event.module}
          </span>
        </div>
      </div>

      {/* Main info */}
      <div className="grid grid-cols-2 gap-4">
        <InfoCard title="Актор">
          <InfoRow label="Пользователь" value={event.actor_username || "—"} />
          <InfoRow label="ID актора" value={event.actor_id || "—"} mono />
          <InfoRow label="IP-адрес" value={event.ip_address || "—"} />
          <InfoRow label="User-Agent" value={event.user_agent || "—"} truncate />
        </InfoCard>

        <InfoCard title="Цель">
          <InfoRow label="Тип" value={event.target_type} />
          <InfoRow label="ID цели" value={event.target_id || "—"} mono />
          <InfoRow label="Операция" value={event.operation} />
          <InfoRow label="Результат" value={event.result} />
        </InfoCard>
      </div>

      {/* Details */}
      {detailEntries.length > 0 && (
        <InfoCard title="Детали события">
          <div className="grid grid-cols-2 gap-x-6">
            {detailEntries.map(([k, v]) => (
              <InfoRow key={k} label={k} value={
                typeof v === "object" ? JSON.stringify(v) : String(v)
              } mono={typeof v === "object"} />
            ))}
          </div>
        </InfoCard>
      )}

      {/* Correlation */}
      <InfoCard title="Трассировка">
        <InfoRow label="correlation_id" value={event.correlation_id || "отсутствует"} mono />
        <InfoRow label="event_id" value={event.event_id} mono />
        <InfoRow label="Опубликовано в Kafka" value={event.published_to_kafka ? "Да" : "Нет"} />
      </InfoCard>

      {/* Correlation chain / Timeline */}
      {event.correlation_id && (
        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <div className="bg-slate-50 px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Связанные события</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                correlation_id: <span className="font-mono">{event.correlation_id}</span>
              </p>
            </div>
            <button
              onClick={openKibana}
              className="text-xs px-3 py-1.5 border border-slate-300 rounded text-slate-600 hover:bg-slate-100 flex items-center gap-1.5"
            >
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Открыть в Kibana
            </button>
          </div>

          {chainLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-3 border-blue-500 border-t-transparent rounded-full" />
            </div>
          ) : chain && chain.events.length > 0 ? (
            <div className="p-5">
              <ol className="relative border-l-2 border-slate-200 ml-3 space-y-0">
                {chain.events.map((ev, idx) => {
                  const isCurrent = ev.event_id === event.event_id;
                  return (
                    <li key={ev.event_id || idx} className="ml-6 pb-6 last:pb-0 relative">
                      {/* Dot */}
                      <span className={`absolute -left-[1.65rem] flex items-center justify-center w-5 h-5 rounded-full border-2
                        ${isCurrent
                          ? "bg-blue-600 border-blue-600"
                          : ev.result === "success"
                            ? "bg-green-500 border-green-500"
                            : ev.result === "failure" || ev.result === "denied"
                              ? "bg-red-400 border-red-400"
                              : "bg-slate-300 border-slate-300"
                        }`}>
                        <span className="text-white text-[9px] font-bold leading-none">
                          {idx + 1}
                        </span>
                      </span>

                      <div className={`rounded-lg border p-3 ${isCurrent ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white"}`}>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${MODULE_COLORS[ev.module || ""] || "bg-slate-100 text-slate-600"}`}>
                            {ev.module || "—"}
                          </span>
                          <span className="text-sm font-semibold text-slate-800">
                            {ev.operation || "—"}
                          </span>
                          <span className={`text-xs font-medium ml-auto ${RESULT_COLORS[ev.result || ""] || "text-slate-500"}`}>
                            {RESULT_ICONS[ev.result || ""] || ""} {ev.result || "—"}
                          </span>
                        </div>
                        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-slate-500">
                          {ev.actor_username && <span>👤 {ev.actor_username}</span>}
                          {ev.target_type && <span>🎯 {ev.target_type}{ev.target_id ? `: ${ev.target_id.slice(0, 12)}` : ""}</span>}
                          {ev.timestamp && <span>🕐 {formatTs(ev.timestamp)}</span>}
                          <span className="text-slate-300">
                            {ev.source === "elasticsearch" ? "ES" : "PG"}
                          </span>
                        </div>
                        {isCurrent && (
                          <span className="mt-1 inline-block text-xs text-blue-600 font-medium">← текущее событие</span>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
              <p className="text-xs text-slate-400 mt-4 ml-6">
                Всего событий в цепочке: {chain.total}
                {chain.events[0]?.source === "elasticsearch" ? " (из Elasticsearch)" : " (из PostgreSQL)"}
              </p>
            </div>
          ) : (
            <div className="py-8 text-center text-slate-400 text-sm">
              Связанные события не найдены
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InfoCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 overflow-hidden">
      <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      </div>
      <div className="px-4 py-3 divide-y divide-slate-100">{children}</div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono,
  truncate,
}: {
  label: string;
  value: string;
  mono?: boolean;
  truncate?: boolean;
}) {
  return (
    <div className="flex items-start gap-2 py-1.5">
      <span className="text-xs text-slate-400 w-28 flex-shrink-0 pt-0.5">{label}</span>
      <span className={`text-xs text-slate-800 min-w-0 ${mono ? "font-mono" : ""} ${truncate ? "truncate" : "break-all"}`}>
        {value}
      </span>
    </div>
  );
}
