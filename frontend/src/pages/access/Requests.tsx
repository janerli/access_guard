import { useEffect, useState } from "react";
import { accessApi, type AccessRequest, type AccessRequestStatus, type Role } from "@/api/access";
import { identityApi, type User } from "@/api/identity";

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

export default function Requests() {
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [allRoles, setAllRoles] = useState<Role[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [newForm, setNewForm] = useState({ user_id: "", role_id: "", justification: "" });
  const [saving, setSaving] = useState(false);
  const [decisionModal, setDecisionModal] = useState<{ req: AccessRequest; action: "approve" | "reject" } | null>(null);
  const [comment, setComment] = useState("");

  const pageSize = 20;

  const load = async () => {
    setLoading(true);
    try {
      const res = await accessApi.listRequests({
        status: statusFilter || undefined,
        page,
        page_size: pageSize,
      });
      setRequests(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  };

  const loadFormData = async () => {
    const [rolesRes, usersRes] = await Promise.all([
      accessApi.listRoles({ page_size: 100 }),
      identityApi.listUsers({ status: "active", page_size: 100 }),
    ]);
    setAllRoles(rolesRes.data.items);
    setAllUsers(usersRes.data.items);
  };

  useEffect(() => { load(); }, [page, statusFilter]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await accessApi.createRequest(newForm);
      setShowCreate(false);
      setNewForm({ user_id: "", role_id: "", justification: "" });
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleDecision = async () => {
    if (!decisionModal) return;
    setSaving(true);
    try {
      if (decisionModal.action === "approve") {
        await accessApi.approveRequest(decisionModal.req.id, comment || undefined);
      } else {
        await accessApi.rejectRequest(decisionModal.req.id, comment || undefined);
      }
      setDecisionModal(null);
      setComment("");
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleWithdraw = async (req: AccessRequest) => {
    if (!confirm("Отозвать заявку?")) return;
    await accessApi.withdrawRequest(req.id);
    load();
  };

  const pages = Math.ceil(total / pageSize);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Заявки на доступ</h1>
          <p className="text-slate-500 text-sm mt-0.5">Всего: {total}</p>
        </div>
        <button
          onClick={() => { loadFormData(); setShowCreate(true); }}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
        >
          + Новая заявка
        </button>
      </div>

      <div className="flex gap-3 flex-wrap">
        {(["", "pending", "approved", "rejected", "withdrawn"] as const).map((s) => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              statusFilter === s ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {s === "" ? "Все" : STATUS_LABELS[s as AccessRequestStatus]}
          </button>
        ))}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <form onSubmit={handleCreate} className="bg-white rounded-xl p-6 w-full max-w-md space-y-4 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-800">Новая заявка на доступ</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Сотрудник</label>
                <select required className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" value={newForm.user_id}
                  onChange={(e) => setNewForm({ ...newForm, user_id: e.target.value })}>
                  <option value="">Выберите сотрудника</option>
                  {allUsers.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name} ({u.username})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Роль</label>
                <select required className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" value={newForm.role_id}
                  onChange={(e) => setNewForm({ ...newForm, role_id: e.target.value })}>
                  <option value="">Выберите роль</option>
                  {allRoles.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Обоснование</label>
                <textarea required className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none" rows={3}
                  value={newForm.justification} onChange={(e) => setNewForm({ ...newForm, justification: e.target.value })}
                  placeholder="Укажите причину запроса доступа..." />
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-600">Отмена</button>
              <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">Отправить</button>
            </div>
          </form>
        </div>
      )}

      {/* Decision modal */}
      {decisionModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md space-y-4 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-800">
              {decisionModal.action === "approve" ? "Одобрить заявку" : "Отклонить заявку"}
            </h2>
            <p className="text-sm text-slate-600">
              Роль: <span className="font-medium">{decisionModal.req.role.name}</span>
            </p>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Комментарий (необязательно)</label>
              <textarea className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm resize-none" rows={3}
                value={comment} onChange={(e) => setComment(e.target.value)} />
            </div>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDecisionModal(null)} className="px-4 py-2 text-sm text-slate-600">Отмена</button>
              <button onClick={handleDecision} disabled={saving}
                className={`px-4 py-2 text-white text-sm rounded-lg disabled:opacity-50 ${
                  decisionModal.action === "approve" ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"
                }`}>
                {decisionModal.action === "approve" ? "Одобрить" : "Отклонить"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Роль</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Обоснование</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Статус</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Дата</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Загрузка...</td></tr>
            ) : requests.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Нет заявок</td></tr>
            ) : requests.map((req) => (
              <tr key={req.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-800">{req.role.name}</td>
                <td className="px-4 py-3 text-slate-500 max-w-xs truncate">{req.justification}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[req.status]}`}>
                    {STATUS_LABELS[req.status]}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500 text-xs">{new Date(req.created_at).toLocaleDateString("ru-RU")}</td>
                <td className="px-4 py-3">
                  {req.status === "pending" && (
                    <div className="flex justify-end gap-2">
                      <button onClick={() => setDecisionModal({ req, action: "approve" })}
                        className="text-xs text-green-600 hover:text-green-800">Одобрить</button>
                      <button onClick={() => setDecisionModal({ req, action: "reject" })}
                        className="text-xs text-red-500 hover:text-red-700">Отклонить</button>
                      <button onClick={() => handleWithdraw(req)}
                        className="text-xs text-slate-400 hover:text-slate-600">Отозвать</button>
                    </div>
                  )}
                  {req.decision_comment && (
                    <p className="text-xs text-slate-400 max-w-xs truncate" title={req.decision_comment}>{req.decision_comment}</p>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: pages }, (_, i) => i + 1).map((p) => (
            <button key={p} onClick={() => setPage(p)}
              className={`w-8 h-8 rounded text-sm ${p === page ? "bg-blue-600 text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
