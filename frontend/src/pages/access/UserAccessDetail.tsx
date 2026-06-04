import { useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { accessApi, type UserRole } from "@/api/access";
import { identityApi, type User } from "@/api/identity";

type EffectivePerms = {
  user_id: string;
  resources: Record<string, { code: string; granted_by_roles: string[] }[]>;
  total: number;
};

function expiresClass(expires_at?: string): string {
  if (!expires_at) return "";
  const diff = new Date(expires_at).getTime() - Date.now();
  if (diff < 0) return "text-red-600 font-semibold";
  if (diff < 7 * 24 * 3600 * 1000) return "text-orange-500 font-semibold";
  return "text-slate-600";
}

function formatDate(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function UserAccessDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [user, setUser] = useState<User | null>(null);
  const [roles, setRoles] = useState<UserRole[]>([]);
  const [effective, setEffective] = useState<EffectivePerms | null>(null);
  const [loading, setLoading] = useState(true);
  const [revoking, setRevoking] = useState<string | null>(null);

  // Check permission dialog
  const [checkOpen, setCheckOpen] = useState(false);
  const [checkCode, setCheckCode] = useState("");
  const [checkResult, setCheckResult] = useState<{ allowed: boolean } | null>(null);
  const [checking, setChecking] = useState(false);

  async function load() {
    if (!id) return;
    const [uRes, rRes, eRes] = await Promise.all([
      identityApi.getUser(id).catch(() => null),
      accessApi.getUserRoles(id).catch(() => ({ data: [] })),
      accessApi.getEffectivePermissions(id).catch(() => null),
    ]);
    setUser(uRes?.data ?? null);
    setRoles(rRes.data);
    setEffective(eRes?.data ?? null);
    setLoading(false);
  }

  useEffect(() => { load(); }, [id]);

  async function handleRevoke(userRoleId: string) {
    if (!id || !window.confirm("Отозвать роль?")) return;
    setRevoking(userRoleId);
    try {
      await accessApi.revokeRole(id, userRoleId);
      await load();
    } finally {
      setRevoking(null);
    }
  }

  async function handleCheck() {
    if (!id || !checkCode.trim()) return;
    setChecking(true);
    setCheckResult(null);
    try {
      const res = await accessApi.checkPermission(id, checkCode.trim());
      setCheckResult({ allowed: res.data.allowed });
    } catch {
      setCheckResult({ allowed: false });
    } finally {
      setChecking(false);
    }
  }

  if (loading) return <div className="p-6 text-muted-foreground">Загрузка...</div>;

  const resourceEntries = Object.entries(effective?.resources ?? {}).sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="p-6 max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/identity/users/${id}`)}
          className="text-sm text-blue-600 hover:underline"
        >
          ← {user?.full_name ?? id}
        </button>
        <span className="text-slate-300">/</span>
        <span className="text-sm font-medium text-slate-700">Роли и полномочия</span>
      </div>

      {/* ── Assigned roles ──────────────────────────────────────── */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Назначенные роли</h2>
        {roles.length === 0 ? (
          <p className="text-sm text-slate-400">Нет назначенных ролей</p>
        ) : (
          <div className="rounded-lg border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-600">Роль</th>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-600">Назначена</th>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-600">Истекает</th>
                  <th className="text-left px-4 py-2.5 font-medium text-slate-600">Основание</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {roles.map(ur => (
                  <tr key={ur.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{ur.role.name}</span>
                        {ur.role.is_privileged && (
                          <span className="px-1.5 py-0.5 text-xs rounded bg-red-100 text-red-700 font-medium">
                            привил.
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-slate-400 font-mono">{ur.role.code}</span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">{formatDate(ur.granted_at)}</td>
                    <td className="px-4 py-2.5">
                      {ur.expires_at ? (
                        <span className={expiresClass(ur.expires_at)}>
                          {formatDate(ur.expires_at)}
                          {new Date(ur.expires_at).getTime() - Date.now() < 7 * 24 * 3600 * 1000 &&
                            new Date(ur.expires_at).getTime() > Date.now() && (
                              <span className="ml-1 text-xs">(скоро)</span>
                            )}
                          {new Date(ur.expires_at).getTime() < Date.now() && (
                            <span className="ml-1 text-xs">(истекла)</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-slate-400">Бессрочно</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      {ur.request_id ? (
                        <Link
                          to={`/access/requests/${ur.request_id}`}
                          className="text-blue-600 hover:underline text-xs font-mono"
                        >
                          Заявка #{ur.request_id.slice(0, 8)}
                        </Link>
                      ) : (
                        <span className="text-xs text-slate-400">Системное назначение</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => handleRevoke(ur.id)}
                        disabled={revoking === ur.id}
                        className="text-xs px-2.5 py-1 border border-red-200 text-red-600 rounded hover:bg-red-50 disabled:opacity-50"
                      >
                        {revoking === ur.id ? "..." : "Отозвать"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-xs text-slate-400">
          Базовые роли по должности отзываются через изменение матрицы должность → роли.
        </p>
      </section>

      {/* ── Effective permissions ────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">
            Эффективные полномочия
            {effective && (
              <span className="ml-2 text-sm font-normal text-slate-400">
                ({effective.total} всего)
              </span>
            )}
          </h2>
        </div>

        {!effective || resourceEntries.length === 0 ? (
          <p className="text-sm text-slate-400">Нет полномочий</p>
        ) : (
          <div className="space-y-3">
            {resourceEntries.map(([resource, perms]) => (
              <div key={resource} className="rounded-lg border overflow-hidden">
                <div className="bg-slate-50 px-4 py-2 border-b">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    {resource}
                  </span>
                </div>
                <div className="divide-y divide-slate-50">
                  {perms.map(p => (
                    <div key={p.code} className="flex items-center justify-between px-4 py-2">
                      <span className="font-mono text-sm text-slate-800">{p.code}</span>
                      <div className="flex flex-wrap gap-1 justify-end max-w-xs">
                        {p.granted_by_roles.map(r => (
                          <span
                            key={r}
                            className="px-1.5 py-0.5 text-xs rounded bg-blue-50 text-blue-700"
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Check permission button ──────────────────────────────── */}
      <div className="pt-2">
        <button
          onClick={() => { setCheckOpen(true); setCheckResult(null); setCheckCode(""); }}
          className="px-4 py-2 bg-slate-800 text-white text-sm rounded hover:bg-slate-700"
        >
          Проверить полномочие
        </button>
      </div>

      {/* ── Check permission dialog ──────────────────────────────── */}
      {checkOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-base font-semibold">Проверить полномочие</h3>
            <p className="text-sm text-slate-500">
              Проверка выполняется через живой кэш Redis. Введите код полномочия в формате{" "}
              <code className="bg-slate-100 px-1 rounded">resource:action</code>.
            </p>
            <input
              type="text"
              placeholder="например: users:read"
              className="w-full border rounded px-3 py-2 text-sm font-mono"
              value={checkCode}
              onChange={e => setCheckCode(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCheck()}
              autoFocus
            />
            {checkResult !== null && (
              <div className={`flex items-center gap-2 px-3 py-2 rounded text-sm font-medium ${
                checkResult.allowed
                  ? "bg-green-50 text-green-700 border border-green-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}>
                <span>{checkResult.allowed ? "Разрешено" : "Запрещено"}</span>
                <span className="font-mono text-xs opacity-70">({checkCode})</span>
              </div>
            )}
            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => setCheckOpen(false)}
                className="px-3 py-1.5 text-sm border rounded hover:bg-slate-50"
              >
                Закрыть
              </button>
              <button
                onClick={handleCheck}
                disabled={checking || !checkCode.trim()}
                className="px-3 py-1.5 text-sm bg-slate-800 text-white rounded hover:bg-slate-700 disabled:opacity-50"
              >
                {checking ? "Проверяю..." : "Проверить"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
