import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { monitorApi, type AuditLogEntry, type AuditOperation, type AuditModule, type AuditResult } from "@/api/monitor";

const RESULT_BADGE: Record<AuditResult, string> = {
  success: "bg-green-100 text-green-800",
  failure: "bg-red-100 text-red-800",
  denied: "bg-orange-100 text-orange-800",
};

export default function AuditLog() {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  const [filters, setFilters] = useState({
    actor_username: "",
    operation: "",
    module: "",
    result: "",
    date_from: "",
    date_to: "",
  });

  const load = async () => {
    try {
      const params: Record<string, unknown> = { page, page_size: PAGE_SIZE };
      if (filters.actor_username) params.actor_username = filters.actor_username;
      if (filters.operation) params.operation = filters.operation;
      if (filters.module) params.module = filters.module;
      if (filters.result) params.result = filters.result;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      const res = await monitorApi.listAudit(params as Parameters<typeof monitorApi.listAudit>[0]);
      setItems(res.data.items);
      setTotal(res.data.total);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => { load(); }, [page, filters]);

  const handleExport = async () => {
    const res = await monitorApi.exportAudit({ fmt: "csv" });
    const url = window.URL.createObjectURL(new Blob([res.data as BlobPart]));
    const a = document.createElement("a");
    a.href = url;
    a.download = "audit.csv";
    a.click();
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Журнал аудита</h1>
        <button onClick={handleExport} className="px-3 py-1.5 text-sm border rounded hover:bg-zinc-50">
          Экспорт CSV
        </button>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-2 bg-white dark:bg-zinc-900 border rounded p-3">
        <input
          className="border rounded px-2 py-1 text-sm"
          placeholder="Пользователь"
          value={filters.actor_username}
          onChange={e => setFilters(f => ({ ...f, actor_username: e.target.value }))}
        />
        <select
          className="border rounded px-2 py-1 text-sm"
          value={filters.operation}
          onChange={e => setFilters(f => ({ ...f, operation: e.target.value }))}
        >
          <option value="">Все операции</option>
          {["login_success","login_failure","create","update","delete","role_assign","role_revoke","password_reset","block","suspend","permission_check"].map(op => (
            <option key={op} value={op}>{op}</option>
          ))}
        </select>
        <select
          className="border rounded px-2 py-1 text-sm"
          value={filters.module}
          onChange={e => setFilters(f => ({ ...f, module: e.target.value }))}
        >
          <option value="">Все модули</option>
          {["auth","identity","access","monitor","reports"].map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select
          className="border rounded px-2 py-1 text-sm"
          value={filters.result}
          onChange={e => setFilters(f => ({ ...f, result: e.target.value }))}
        >
          <option value="">Все результаты</option>
          <option value="success">success</option>
          <option value="failure">failure</option>
          <option value="denied">denied</option>
        </select>
        <input
          type="datetime-local"
          className="border rounded px-2 py-1 text-sm"
          value={filters.date_from}
          onChange={e => setFilters(f => ({ ...f, date_from: e.target.value }))}
        />
        <input
          type="datetime-local"
          className="border rounded px-2 py-1 text-sm"
          value={filters.date_to}
          onChange={e => setFilters(f => ({ ...f, date_to: e.target.value }))}
        />
      </div>

      {/* Table */}
      <div className="border rounded overflow-x-auto bg-white dark:bg-zinc-900">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-800">
            <tr>
              <th className="text-left px-3 py-2">Время</th>
              <th className="text-left px-3 py-2">Пользователь</th>
              <th className="text-left px-3 py-2">Операция</th>
              <th className="text-left px-3 py-2">Модуль</th>
              <th className="text-left px-3 py-2">Объект</th>
              <th className="text-left px-3 py-2">Результат</th>
              <th className="text-left px-3 py-2">IP</th>
            </tr>
          </thead>
          <tbody>
            {items.map(item => (
              <tr key={item.id} className="border-t hover:bg-zinc-50 dark:hover:bg-zinc-800">
                <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">
                  {new Date(item.timestamp).toLocaleString("ru")}
                </td>
                <td className="px-3 py-2">
                  <Link to={`/monitor/audit/${item.event_id}`} className="hover:underline text-blue-600">
                    {item.actor_username || "—"}
                  </Link>
                </td>
                <td className="px-3 py-2 font-mono text-xs">{item.operation}</td>
                <td className="px-3 py-2 text-xs">{item.module}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{item.target_type}/{item.target_id || "—"}</td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${RESULT_BADGE[item.result]}`}>
                    {item.result}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs text-muted-foreground">{item.ip_address || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="text-center text-muted-foreground py-8">Событий не найдено</p>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Всего: {total}</span>
        <div className="flex gap-2">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 border rounded disabled:opacity-40">← Назад</button>
          <span className="px-2 py-1">{page} / {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 border rounded disabled:opacity-40">Вперёд →</button>
        </div>
      </div>
    </div>
  );
}
