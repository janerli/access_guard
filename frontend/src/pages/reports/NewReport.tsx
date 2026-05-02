import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { reportsApi, type ReportFormat, type ReportTemplate } from "@/api/reports";

export default function NewReport() {
  const { templateCode } = useParams<{ templateCode: string }>();
  const navigate = useNavigate();
  const [template, setTemplate] = useState<ReportTemplate | null>(null);
  const [format, setFormat] = useState<ReportFormat>("xlsx");
  const [params, setParams] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!templateCode) return;
    reportsApi.getTemplate(templateCode).then(r => {
      setTemplate(r.data);
      setFormat((r.data.output_formats[0] as ReportFormat) || "xlsx");
      setLoading(false);
    });
  }, [templateCode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await reportsApi.createReport({
        template_code: templateCode!,
        parameters: params,
        format,
      });
      navigate(`/reports/history?highlight=${res.data.id}`);
    } catch (err: unknown) {
      setError("Ошибка создания отчёта");
    } finally {
      setSubmitting(false);
    }
  };

  const schema = template?.parameters_schema as { properties?: Record<string, { title?: string; type?: string; format?: string; enum?: string[] }> } | null;
  const properties = schema?.properties || {};

  if (loading) return <div className="p-6 text-muted-foreground">Загрузка...</div>;
  if (!template) return <div className="p-6 text-red-500">Шаблон не найден</div>;

  return (
    <div className="p-6 max-w-xl">
      <button onClick={() => navigate("/reports/templates")} className="text-sm text-blue-600 hover:underline mb-4 block">
        ← Назад к шаблонам
      </button>
      <h1 className="text-2xl font-bold mb-2">{template.name}</h1>
      <p className="text-muted-foreground mb-6">{template.description}</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Dynamic parameter fields */}
        {Object.entries(properties).map(([key, prop]) => (
          <div key={key}>
            <label className="block text-sm font-medium mb-1">
              {prop.title || key}
            </label>
            {prop.enum ? (
              <select
                className="w-full border rounded px-3 py-2 text-sm"
                value={params[key] || ""}
                onChange={e => setParams(p => ({ ...p, [key]: e.target.value }))}
              >
                <option value="">— Не выбрано —</option>
                {prop.enum.map(v => <option key={v} value={v}>{v}</option>)}
              </select>
            ) : (
              <input
                type={prop.format === "date" ? "date" : prop.type === "integer" ? "number" : "text"}
                className="w-full border rounded px-3 py-2 text-sm"
                value={params[key] || ""}
                onChange={e => setParams(p => ({ ...p, [key]: e.target.value }))}
                placeholder={prop.title || key}
              />
            )}
          </div>
        ))}

        {/* Format selector */}
        <div>
          <label className="block text-sm font-medium mb-1">Формат</label>
          <div className="flex gap-2">
            {template.output_formats.map(fmt => (
              <button
                type="button"
                key={fmt}
                onClick={() => setFormat(fmt as ReportFormat)}
                className={`px-4 py-2 rounded border text-sm font-mono transition-colors ${
                  format === fmt
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-zinc-300 hover:border-blue-400"
                }`}
              >
                {fmt.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full py-2.5 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {submitting ? "Формирование..." : "Сформировать отчёт"}
        </button>
      </form>
    </div>
  );
}
