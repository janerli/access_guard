import { useEffect, useState } from "react";
import { monitorApi } from "@/api/monitor";

export default function KibanaPage() {
  const [embedUrl, setEmbedUrl] = useState<string | null>(null);

  useEffect(() => {
    monitorApi.getKibanaToken().then(res => {
      setEmbedUrl(res.data.embed_url);
    }).catch(() => {
      setEmbedUrl("http://localhost:5601");
    });
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-3 border-b flex items-center justify-between">
        <h1 className="text-xl font-bold">Kibana — Аналитика аудита</h1>
        {embedUrl && (
          <a href={embedUrl} target="_blank" rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline">
            Открыть в новой вкладке ↗
          </a>
        )}
      </div>
      {embedUrl ? (
        <iframe
          src={embedUrl}
          className="flex-1 w-full border-0"
          title="Kibana Dashboards"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          Загрузка...
        </div>
      )}
    </div>
  );
}
