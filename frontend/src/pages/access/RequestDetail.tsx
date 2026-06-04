import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { accessApi, type AccessRequest, type AccessRequestStatus } from "@/api/access";

const STATUS_LABELS: Record<AccessRequestStatus, string> = {
  pending: "Ожидает",
  approved: "Одобрена",
  rejected: "Отклонена",
  withdrawn: "Отозвана",
};

const STATUS_COLORS: Record<AccessRequestStatus, string> = {
  pending: "bg-yellow-50 text-yellow-700",
  approved: "bg-green-50 text-green-700",
  rejected: "bg-red-50 text-red-700",
  withdrawn: "bg-slate-100 text-slate-600",
};

function fmt(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("ru");
}

export default function RequestDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [req, setReq] = useState<AccessRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    accessApi.getRequest(id)
      .then(r => setReq(r.data))
      .catch(() => setError("Заявка не найдена"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="p-6 text-muted-foreground">Загрузка...</div>;
  if (error || !req) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-500 text-lg">{error || "Заявка не найдена"}</p>
        <button onClick={() => navigate("/access/requests")} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
          ← К списку заявок
        </button>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl space-y-5">
      <button onClick={() => navigate("/access/requests")} className="text-sm text-blue-600 hover:underline">
        ← К списку заявок
      </button>

      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Заявка на доступ</h1>
        <span className={`px-2 py-0.5 rounded text-sm font-medium ${STATUS_COLORS[req.status]}`}>
          {STATUS_LABELS[req.status]}
        </span>
      </div>

      <div className="rounded-lg border divide-y">
        <Row label="ID заявки" value={req.id} mono />
        <Row label="Роль" value={req.role?.name || req.role_id} />
        <Row label="Пользователь (ID)" value={req.user_id} mono />
        <Row label="Обоснование" value={req.justification} />
        <Row label="Создана" value={fmt(req.created_at)} />
        <Row label="Решение принято" value={fmt(req.decided_at)} />
        {req.decision_comment && <Row label="Комментарий" value={req.decision_comment} />}
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-3 px-4 py-2.5">
      <span className="text-sm text-slate-500 w-44 flex-shrink-0">{label}</span>
      <span className={`text-sm text-slate-800 break-all ${mono ? "font-mono text-xs" : ""}`}>{value}</span>
    </div>
  );
}
