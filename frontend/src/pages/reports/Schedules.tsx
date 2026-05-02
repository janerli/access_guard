import { useEffect, useState } from "react";
import { reportsApi, type ReportSchedule, type ReportTemplate } from "@/api/reports";

export default function ReportSchedules() {
  const [schedules, setSchedules] = useState<ReportSchedule[]>([]);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    template_code: "",
    format: "xlsx" as "pdf" | "xlsx" | "csv",
    cron_expression: "@daily",
    is_enabled: true,
  });

  const load = async () => {
    const [sch, tmpl] = await Promise.all([
      reportsApi.listSchedules(),
      reportsApi.listTemplates(),
    ]);
    setSchedules(sch.data);
    setTemplates(tmpl.data);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await reportsApi.createSchedule({ ...form, parameters: {} });
    setShowForm(false);
    load();
  };

  const handleToggle = async (s: ReportSchedule) => {
    await reportsApi.updateSchedule(s.id, { is_enabled: !s.is_enabled });
    load();
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Удалить расписание?")) return;
    await reportsApi.deleteSchedule(id);
    load();
  };

  const handleRunNow = async (id: string) => {
    await reportsApi.runScheduleNow(id);
    load();
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Расписания отчётов</h1>
        <button
          onClick={() => setShowForm(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
        >
          + Добавить
        </button>
      </div>

      <div className="space-y-3">
        {schedules.map(s => (
          <div key={s.id} className={`bg-white dark:bg-zinc-900 border rounded-lg p-4 ${!s.is_enabled ? "opacity-60" : ""}`}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium">{s.template?.name || s.template_id.slice(0, 8)}</p>
                <div className="flex gap-3 mt-1 text-sm text-muted-foreground">
                  <span className="font-mono">{s.cron_expression}</span>
                  <span className="uppercase">{s.format}</span>
                  {s.last_run_at && (
                    <span>Запуск: {new Date(s.last_run_at).toLocaleString("ru")}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => handleRunNow(s.id)}
                  className="px-2 py-1 text-xs border rounded hover:bg-zinc-50">
                  Запустить
                </button>
                <button onClick={() => handleToggle(s)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${s.is_enabled ? "bg-blue-600" : "bg-zinc-300"}`}>
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${s.is_enabled ? "translate-x-6" : "translate-x-1"}`} />
                </button>
                <button onClick={() => handleDelete(s.id)}
                  className="px-2 py-1 text-xs border border-red-200 text-red-600 rounded hover:bg-red-50">
                  Удалить
                </button>
              </div>
            </div>
          </div>
        ))}
        {schedules.length === 0 && (
          <p className="text-center text-muted-foreground py-8">Расписаний нет</p>
        )}
      </div>

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-6 w-full max-w-md shadow-xl">
            <h2 className="font-semibold mb-4">Новое расписание</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">Шаблон</label>
                <select required className="w-full border rounded px-3 py-2 text-sm"
                  value={form.template_code}
                  onChange={e => setForm(f => ({ ...f, template_code: e.target.value }))}>
                  <option value="">— Выберите шаблон —</option>
                  {templates.map(t => <option key={t.code} value={t.code}>{t.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Формат</label>
                <select className="w-full border rounded px-3 py-2 text-sm"
                  value={form.format}
                  onChange={e => setForm(f => ({ ...f, format: e.target.value as "pdf" | "xlsx" | "csv" }))}>
                  <option value="xlsx">XLSX</option>
                  <option value="pdf">PDF</option>
                  <option value="csv">CSV</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Расписание</label>
                <select className="w-full border rounded px-3 py-2 text-sm"
                  value={form.cron_expression}
                  onChange={e => setForm(f => ({ ...f, cron_expression: e.target.value }))}>
                  <option value="@hourly">Каждый час</option>
                  <option value="@daily">Каждый день</option>
                  <option value="@weekly">Каждую неделю</option>
                  <option value="09:00">Каждый день в 09:00</option>
                  <option value="18:00">Каждый день в 18:00</option>
                </select>
              </div>
              <div className="flex gap-2 pt-2 justify-end">
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded text-sm">Отмена</button>
                <button type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                  Создать
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
