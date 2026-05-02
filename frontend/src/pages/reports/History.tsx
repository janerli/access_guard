import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { reportsApi, type Report, type ReportStatus } from "@/api/reports";

const STATUS_STYLE: Record<ReportStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  generating: "bg-blue-100 text-blue-800",
  ready: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

const STATUS_LABEL: Record<ReportStatus, string> = {
  pending: "В очереди",
  generating: "Формируется...",
  ready: "Готов",
  failed: "Ошибка",
};

export default function ReportHistory() {
  const [items, setItems] = useState<Report[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [searchParams] = useSearchParams();
  const highlight = searchParams.get("highlight");
  const wsRef = useRef<WebSocket | null>(null);

  const load = async () => {
    const res = await reportsApi.listReports({ page, page_size: 20 });
    setItems(res.data.items);
    setTotal(res.data.total);
  };

  useEffect(() => {
    load();
    // WebSocket for live status updates
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/reports/ws/reports`);
    wsRef.current = ws;
    ws.onmessage = () => load();
    return () => ws.close();
  }, [page]);

  const handleDownload = async (report: Report) => {
    const res = await reportsApi.downloadReport(report.id);
    const url = window.URL.createObjectURL(new Blob([res.data as BlobPart]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${report.id.slice(0, 8)}.${report.format}`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">История отчётов</h1>
        <button onClick={load} className="px-3 py-1.5 text-sm border rounded hover:bg-zinc-50">
          Обновить
        </button>
      </div>

      <div className="border rounded bg-white dark:bg-zinc-900 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-800">
            <tr>
              <th className="text-left px-4 py-2">Шаблон</th>
              <th className="text-left px-4 py-2">Формат</th>
              <th className="text-left px-4 py-2">Статус</th>
              <th className="text-left px-4 py-2">Создан</th>
              <th className="text-left px-4 py-2">Готов</th>
              <th className="text-left px-4 py-2">Размер</th>
              <th className="text-left px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map(report => (
              <tr
                key={report.id}
                className={`border-t ${highlight === report.id ? "bg-blue-50" : "hover:bg-zinc-50 dark:hover:bg-zinc-800"}`}
              >
                <td className="px-4 py-2 font-medium">
                  {report.template?.name || report.template_id.slice(0, 8)}
                </td>
                <td className="px-4 py-2 font-mono text-xs uppercase">{report.format}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLE[report.status]}`}>
                    {STATUS_LABEL[report.status]}
                  </span>
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {new Date(report.created_at).toLocaleString("ru")}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {report.completed_at ? new Date(report.completed_at).toLocaleString("ru") : "—"}
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground">
                  {report.file_size ? `${Math.round(report.file_size / 1024)} KB` : "—"}
                </td>
                <td className="px-4 py-2">
                  {report.status === "ready" && (
                    <button
                      onClick={() => handleDownload(report)}
                      className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      Скачать
                    </button>
                  )}
                  {report.status === "failed" && (
                    <span className="text-xs text-red-500" title={report.error_message || ""}>
                      Ошибка
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="text-center text-muted-foreground py-8">Отчётов пока нет</p>
        )}
      </div>

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
    </div>
  );
}
