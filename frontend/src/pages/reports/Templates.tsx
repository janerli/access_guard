import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { reportsApi, type ReportTemplate } from "@/api/reports";

const SOURCE_BADGE: Record<string, string> = {
  postgres: "bg-blue-100 text-blue-800",
  elasticsearch: "bg-purple-100 text-purple-800",
  combined: "bg-green-100 text-green-800",
};

export default function ReportTemplates() {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    reportsApi.listTemplates().then(r => {
      setTemplates(r.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-6 text-muted-foreground">Загрузка...</div>;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Шаблоны отчётов</h1>
        <button
          onClick={() => navigate("/reports/history")}
          className="px-3 py-1.5 text-sm border rounded hover:bg-zinc-50"
        >
          История отчётов
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {templates.map(tmpl => (
          <div key={tmpl.id} className="bg-white dark:bg-zinc-900 border rounded-lg p-4 hover:border-blue-400 transition-colors">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="font-semibold">{tmpl.name}</h2>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${SOURCE_BADGE[tmpl.data_source]}`}>
                    {tmpl.data_source}
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{tmpl.description}</p>
                <div className="mt-2 flex gap-1">
                  {tmpl.output_formats.map(fmt => (
                    <span key={fmt} className="px-1.5 py-0.5 bg-zinc-100 text-zinc-700 text-xs rounded font-mono">
                      {fmt.toUpperCase()}
                    </span>
                  ))}
                </div>
              </div>
              <button
                onClick={() => navigate(`/reports/new/${tmpl.code}`)}
                className="shrink-0 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
              >
                Сформировать
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
