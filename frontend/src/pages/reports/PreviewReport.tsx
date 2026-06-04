import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { reportsApi, type Report } from "@/api/reports";

const STATUS_LABEL: Record<string, string> = {
  pending: "В очереди",
  generating: "Формируется...",
  ready: "Готов",
  failed: "Ошибка",
};

const STATUS_COLOR: Record<string, string> = {
  pending: "text-yellow-600 bg-yellow-50",
  generating: "text-blue-600 bg-blue-50",
  ready: "text-green-600 bg-green-50",
  failed: "text-red-600 bg-red-50",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export default function PreviewReport() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const fetchOnce = async () => {
      try {
        const r = await reportsApi.getReport(id);
        if (cancelled) return;
        setReport(r.data);
        // Пока отчёт генерируется — опрашиваем каждые 2с (Celery асинхронный).
        if (r.data.status === "pending" || r.data.status === "generating") {
          timer = setTimeout(fetchOnce, 2000);
        }
      } catch {
        if (!cancelled) setError("Отчёт не найден");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchOnce();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [id]);

  // Загружаем PDF через API (с JWT) и создаём blob URL для iframe
  useEffect(() => {
    if (!report || report.format !== "pdf" || report.status !== "ready") return;
    let url: string;
    reportsApi.downloadReport(report.id).then(res => {
      url = URL.createObjectURL(new Blob([res.data as BlobPart], { type: "application/pdf" }));
      setPdfBlobUrl(url);
    }).catch(() => setPdfBlobUrl(null));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [report?.id, report?.status]);

  const handleDownload = async () => {
    if (!report) return;
    const res = await reportsApi.downloadReport(report.id);
    const url = window.URL.createObjectURL(new Blob([res.data as BlobPart]));
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${report.id.slice(0, 8)}.${report.format}`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const handleRegenerate = async () => {
    if (!report?.template) return;
    setRegenerating(true);
    try {
      const res = await reportsApi.createReport({
        template_code: report.template.code,
        parameters: report.parameters,
        format: report.format,
      });
      navigate(`/reports/preview/${res.data.id}`);
    } catch {
      setError("Не удалось создать отчёт");
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-12">
        <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500 text-lg">{error || "Отчёт не найден"}</p>
        <button onClick={() => navigate("/reports/history")} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          ← К истории отчётов
        </button>
      </div>
    );
  }

  const isPdf = report.format === "pdf";
  const isReady = report.status === "ready";

  const paramEntries = Object.entries(report.parameters || {});

  return (
    <div className="flex h-full">
      {/* ── Left panel: PDF viewer (65%) ─────────────────────────────────── */}
      <div className="flex-[65] flex flex-col border-r border-slate-200 min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-3 px-4 py-3 bg-slate-50 border-b border-slate-200">
          <button
            onClick={() => navigate("/reports/history")}
            className="text-slate-500 hover:text-slate-800 text-sm flex items-center gap-1"
          >
            ← Назад
          </button>
          <span className="text-slate-300">|</span>
          <span className="text-sm font-medium text-slate-700 truncate">
            {report.template?.name || "Отчёт"}
          </span>
          <span className={`ml-auto text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLOR[report.status]}`}>
            {STATUS_LABEL[report.status]}
          </span>
        </div>

        {/* Viewer */}
        <div className="flex-1 bg-slate-100 overflow-hidden">
          {isReady && isPdf ? (
            pdfBlobUrl ? (
              <iframe
                src={pdfBlobUrl}
                className="w-full h-full border-none"
                title="PDF предпросмотр"
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
              </div>
            )
          ) : isReady && !isPdf ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
              <svg className="w-16 h-16 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-lg font-medium">
                Предпросмотр недоступен для формата <span className="uppercase font-bold">{report.format}</span>
              </p>
              <button
                onClick={handleDownload}
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
              >
                Скачать файл
              </button>
            </div>
          ) : report.status === "generating" || report.status === "pending" ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-slate-500">
              <div className="animate-spin w-12 h-12 border-4 border-blue-400 border-t-transparent rounded-full" />
              <p className="text-lg">{STATUS_LABEL[report.status]}</p>
              <p className="text-sm text-slate-400">Страница обновится автоматически</p>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500">
              <svg className="w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-lg font-medium text-red-500">Ошибка генерации</p>
              {report.error_message && (
                <p className="text-sm text-slate-400 max-w-md text-center">{report.error_message}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel: metadata (35%) ───────────────────────────────────── */}
      <div className="flex-[35] flex flex-col overflow-y-auto min-w-0 bg-white">
        <div className="p-5 space-y-5">

          {/* Action buttons */}
          <div className="flex flex-col gap-2">
            {isReady && (
              <button
                onClick={handleDownload}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium text-sm"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Скачать {report.format.toUpperCase()}
              </button>
            )}
            <button
              onClick={handleRegenerate}
              disabled={regenerating || !report.template}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 font-medium text-sm disabled:opacity-50"
            >
              <svg className={`w-4 h-4 ${regenerating ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {regenerating ? "Создаётся..." : "Сформировать повторно"}
            </button>
          </div>

          {/* Metadata card */}
          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200">
              <h3 className="text-sm font-semibold text-slate-700">Метаданные</h3>
            </div>
            <div className="divide-y divide-slate-100">
              <MetaRow label="Шаблон" value={report.template?.name || "—"} />
              <MetaRow label="Формат" value={report.format.toUpperCase()} />
              <MetaRow label="Статус">
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLOR[report.status]}`}>
                  {STATUS_LABEL[report.status]}
                </span>
              </MetaRow>
              <MetaRow label="Создан" value={new Date(report.created_at).toLocaleString("ru")} />
              {report.completed_at && (
                <MetaRow label="Завершён" value={new Date(report.completed_at).toLocaleString("ru")} />
              )}
              {report.file_size != null && (
                <MetaRow label="Размер файла" value={formatBytes(report.file_size)} />
              )}
              <MetaRow label="ID" value={report.id} mono />
            </div>
          </div>

          {/* Parameters */}
          {paramEntries.length > 0 && (
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200">
                <h3 className="text-sm font-semibold text-slate-700">Параметры</h3>
              </div>
              <div className="divide-y divide-slate-100">
                {paramEntries.map(([k, v]) => (
                  <MetaRow key={k} label={k} value={String(v)} />
                ))}
              </div>
            </div>
          )}

          {/* Template description */}
          {report.template?.description && (
            <div className="rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-1.5">Описание шаблона</h3>
              <p className="text-sm text-slate-500">{report.template.description}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetaRow({
  label,
  value,
  mono,
  children,
}: {
  label: string;
  value?: string;
  mono?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 px-4 py-2.5">
      <span className="text-xs text-slate-500 w-28 flex-shrink-0 pt-0.5">{label}</span>
      {children ?? (
        <span className={`text-xs text-slate-800 break-all ${mono ? "font-mono" : ""}`}>
          {value ?? "—"}
        </span>
      )}
    </div>
  );
}
