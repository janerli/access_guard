import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { reportsApi, type ReportFormat, type ReportTemplate } from "@/api/reports";
import { identityApi, type Department, type Position } from "@/api/identity";

// Статические enum для полей которые не загружаются из API
const STATIC_ENUMS: Record<string, { label: string; value: string }[]> = {
  severity: [
    { value: "low",      label: "Низкая (low)" },
    { value: "medium",   label: "Средняя (medium)" },
    { value: "high",     label: "Высокая (high)" },
    { value: "critical", label: "Критическая (critical)" },
  ],
  status: [
    { value: "pending",   label: "Ожидает (pending)" },
    { value: "approved",  label: "Одобрена (approved)" },
    { value: "rejected",  label: "Отклонена (rejected)" },
    { value: "cancelled", label: "Отменена (cancelled)" },
  ],
};

type PropSchema = {
  title?: string;
  type?: string;
  format?: string;
  enum?: string[];
  default?: string | number;
};

export default function NewReport() {
  const { templateCode } = useParams<{ templateCode: string }>();
  const navigate = useNavigate();

  const [template, setTemplate] = useState<ReportTemplate | null>(null);
  const [format, setFormat] = useState<ReportFormat>("xlsx");
  const [params, setParams] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Динамические справочники
  const [departments, setDepartments] = useState<Department[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);

  useEffect(() => {
    if (!templateCode) return;
    Promise.all([
      reportsApi.getTemplate(templateCode),
      identityApi.listDepartments(),
      identityApi.listPositions(),
    ]).then(([tmplRes, depsRes, posRes]) => {
      setTemplate(tmplRes.data);
      setFormat((tmplRes.data.output_formats[0] as ReportFormat) || "xlsx");
      setDepartments(depsRes.data);
      setPositions(posRes.data);
      setLoading(false);
    }).catch(() => setLoading(false));
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
    } catch {
      setError("Ошибка создания отчёта");
    } finally {
      setSubmitting(false);
    }
  };

  const setParam = (key: string, value: string) =>
    setParams(p => ({ ...p, [key]: value }));

  const schema = template?.parameters_schema as {
    properties?: Record<string, PropSchema>;
    required?: string[];
  } | null;
  const properties = schema?.properties || {};
  const required = schema?.required || [];

  if (loading) return <div className="p-6 text-muted-foreground">Загрузка...</div>;
  if (!template) return <div className="p-6 text-red-500">Шаблон не найден</div>;

  const renderField = (key: string, prop: PropSchema) => {
    const value = params[key] ?? String(prop.default ?? "");
    const isRequired = required.includes(key);
    const label = (
      <label className="block text-sm font-medium mb-1">
        {prop.title || key}
        {isRequired && <span className="text-red-500 ml-1">*</span>}
      </label>
    );

    // 1. department_id — динамический список отделов
    if (key === "department_id") {
      return (
        <div key={key}>
          {label}
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-white dark:bg-zinc-900"
            value={value}
            onChange={e => setParam(key, e.target.value)}
          >
            <option value="">— Все отделы —</option>
            {departments.map(d => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </div>
      );
    }

    // 2. position_id — динамический список должностей
    if (key === "position_id") {
      return (
        <div key={key}>
          {label}
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-white dark:bg-zinc-900"
            value={value}
            onChange={e => setParam(key, e.target.value)}
          >
            <option value="">— Все должности —</option>
            {positions.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      );
    }

    // 3. Поля с enum из схемы (например status в users_report)
    if (prop.enum && prop.enum.length > 0) {
      return (
        <div key={key}>
          {label}
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-white dark:bg-zinc-900"
            value={value}
            onChange={e => setParam(key, e.target.value)}
          >
            <option value="">— Не выбрано —</option>
            {prop.enum.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      );
    }

    // 4. Статические enum по имени поля (severity, status для заявок)
    if (STATIC_ENUMS[key]) {
      return (
        <div key={key}>
          {label}
          <select
            className="w-full border rounded px-3 py-2 text-sm bg-white dark:bg-zinc-900"
            value={value}
            onChange={e => setParam(key, e.target.value)}
          >
            <option value="">— Не выбрано —</option>
            {STATIC_ENUMS[key].map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      );
    }

    // 5. Дата
    if (prop.format === "date") {
      return (
        <div key={key}>
          {label}
          <input
            type="date"
            className="w-full border rounded px-3 py-2 text-sm"
            value={value}
            required={isRequired}
            onChange={e => setParam(key, e.target.value)}
          />
        </div>
      );
    }

    // 6. Число
    if (prop.type === "integer") {
      return (
        <div key={key}>
          {label}
          <input
            type="number"
            className="w-full border rounded px-3 py-2 text-sm"
            value={value}
            required={isRequired}
            min={1}
            onChange={e => setParam(key, e.target.value)}
            placeholder={prop.title || key}
          />
        </div>
      );
    }

    // 7. Обычный текст
    return (
      <div key={key}>
        {label}
        <input
          type="text"
          className="w-full border rounded px-3 py-2 text-sm"
          value={value}
          required={isRequired}
          onChange={e => setParam(key, e.target.value)}
          placeholder={prop.title || key}
        />
      </div>
    );
  };

  return (
    <div className="p-6 max-w-xl">
      <button
        onClick={() => navigate("/reports/templates")}
        className="text-sm text-blue-600 hover:underline mb-4 block"
      >
        ← Назад к шаблонам
      </button>
      <h1 className="text-2xl font-bold mb-2">{template.name}</h1>
      <p className="text-muted-foreground mb-6">{template.description}</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        {Object.entries(properties).map(([key, prop]) => renderField(key, prop))}

        {/* Формат */}
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
