import { useEffect, useState } from "react";
import { identityApi, type LifecycleEvent } from "@/api/identity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const EVENT_LABELS: Record<string, string> = {
  hire: "Приём", transfer: "Перевод", leave_start: "Начало отпуска",
  leave_end: "Конец отпуска", terminate: "Увольнение",
};

export default function Events() {
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [loading, setLoading] = useState(false);

  const PAGE_SIZE = 20;

  async function load() {
    setLoading(true);
    try {
      const resp = await identityApi.listEvents({
        event_type: typeFilter || undefined,
        page,
      });
      setEvents(resp.data.items);
      setTotal(resp.data.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [page, typeFilter]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold text-slate-800">Кадровые события</h1>

      <div className="flex gap-3">
        <select
          className="border rounded px-3 py-2 text-sm"
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
        >
          <option value="">Все типы</option>
          {Object.entries(EVENT_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium text-slate-600">Всего: {total}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Событие</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Источник</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Статус</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Дата</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Данные</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Загрузка...</td></tr>
              ) : events.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Нет событий</td></tr>
              ) : events.map((ev) => (
                <tr key={ev.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium">{EVENT_LABELS[ev.event_type] ?? ev.event_type}</td>
                  <td className="px-4 py-3 text-slate-500">{ev.source}</td>
                  <td className="px-4 py-3">
                    <Badge variant={ev.status === "processed" ? "default" : ev.status === "failed" ? "destructive" : "secondary"}>
                      {ev.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{new Date(ev.created_at).toLocaleString("ru-RU")}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs max-w-xs truncate">
                    {ev.payload?.full_name as string ?? ev.payload?.employee_id as string ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex gap-2 justify-center">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>←</Button>
          <span className="text-sm text-slate-600 self-center">{page} / {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>→</Button>
        </div>
      )}
    </div>
  );
}
