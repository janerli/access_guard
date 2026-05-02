import { useEffect, useState } from "react";
import { monitorApi, type Alert, type AlertSeverity, type AlertStatus } from "@/api/monitor";

const SEVERITY_STYLE: Record<AlertSeverity, string> = {
  info: "bg-blue-100 text-blue-800",
  low: "bg-zinc-100 text-zinc-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

const STATUS_STYLE: Record<AlertStatus, string> = {
  new: "bg-red-50 text-red-700 border border-red-200",
  acknowledged: "bg-yellow-50 text-yellow-700 border border-yellow-200",
  resolved: "bg-green-50 text-green-700 border border-green-200",
  false_positive: "bg-zinc-50 text-zinc-500 border border-zinc-200",
};

export default function Alerts() {
  const [items, setItems] = useState<Alert[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const [activeAlert, setActiveAlert] = useState<Alert | null>(null);
  const [comment, setComment] = useState("");
  const [action, setAction] = useState<"acknowledge" | "resolve" | "false_positive" | null>(null);

  const load = async () => {
    const params: Record<string, unknown> = { page, page_size: 20 };
    if (filterStatus) params.status = filterStatus;
    if (filterSeverity) params.severity = filterSeverity;
    const res = await monitorApi.listAlerts(params as Parameters<typeof monitorApi.listAlerts>[0]);
    setItems(res.data.items);
    setTotal(res.data.total);
  };

  useEffect(() => { load(); }, [page, filterStatus, filterSeverity]);

  const handleAction = async () => {
    if (!activeAlert || !action) return;
    if (action === "acknowledge") await monitorApi.acknowledgeAlert(activeAlert.id, comment);
    if (action === "resolve") await monitorApi.resolveAlert(activeAlert.id, comment);
    if (action === "false_positive") await monitorApi.markFalsePositive(activeAlert.id, comment);
    setActiveAlert(null);
    setComment("");
    setAction(null);
    load();
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold">Оповещения</h1>

      {/* Filters */}
      <div className="flex gap-3">
        <select className="border rounded px-2 py-1 text-sm"
          value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">Все статусы</option>
          <option value="new">Новые</option>
          <option value="acknowledged">В работе</option>
          <option value="resolved">Закрытые</option>
          <option value="false_positive">Ложные</option>
        </select>
        <select className="border rounded px-2 py-1 text-sm"
          value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}>
          <option value="">Все severity</option>
          {["critical","high","medium","low","info"].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {/* Cards */}
      <div className="space-y-3">
        {items.map(alert => (
          <div key={alert.id} className={`rounded-lg border p-4 ${STATUS_STYLE[alert.status]}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-2 py-0.5 rounded text-xs font-bold ${SEVERITY_STYLE[alert.severity]}`}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <span className="font-medium text-sm truncate">
                    {alert.rule?.name || alert.rule_id}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {new Date(alert.triggered_at).toLocaleString("ru")}
                  </span>
                </div>
                {Object.keys(alert.details).length > 0 && (
                  <pre className="mt-2 text-xs bg-white/60 rounded p-2 overflow-x-auto">
                    {JSON.stringify(alert.details, null, 2)}
                  </pre>
                )}
                {alert.resolution_comment && (
                  <p className="mt-1 text-xs italic">{alert.resolution_comment}</p>
                )}
              </div>
              {alert.status === "new" && (
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => { setActiveAlert(alert); setAction("acknowledge"); }}
                    className="px-2 py-1 text-xs border rounded bg-white hover:bg-zinc-50">
                    Взять в работу
                  </button>
                  <button onClick={() => { setActiveAlert(alert); setAction("resolve"); }}
                    className="px-2 py-1 text-xs border rounded bg-white hover:bg-zinc-50">
                    Закрыть
                  </button>
                  <button onClick={() => { setActiveAlert(alert); setAction("false_positive"); }}
                    className="px-2 py-1 text-xs border rounded bg-white hover:bg-zinc-50 text-zinc-500">
                    Ложное
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-center text-muted-foreground py-12">Оповещений нет</p>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Всего: {total}</span>
        <div className="flex gap-2">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 border rounded disabled:opacity-40">← Назад</button>
          <span className="px-2 py-1">{page} / {Math.max(totalPages, 1)}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 border rounded disabled:opacity-40">Вперёд →</button>
        </div>
      </div>

      {/* Action modal */}
      {activeAlert && action && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-6 w-full max-w-md shadow-xl">
            <h2 className="font-semibold mb-4">
              {action === "acknowledge" && "Взять в работу"}
              {action === "resolve" && "Закрыть оповещение"}
              {action === "false_positive" && "Ложное срабатывание"}
            </h2>
            <textarea
              className="w-full border rounded px-3 py-2 text-sm h-24"
              placeholder="Комментарий (необязательно)"
              value={comment}
              onChange={e => setComment(e.target.value)}
            />
            <div className="flex gap-2 mt-4 justify-end">
              <button onClick={() => setActiveAlert(null)}
                className="px-4 py-2 border rounded text-sm">Отмена</button>
              <button onClick={handleAction}
                className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
