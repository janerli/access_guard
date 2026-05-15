import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { identityApi, type LifecycleEvent, type User } from "@/api/identity";
import { accessApi, type UserRole, type Role } from "@/api/access";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STATUS_LABELS: Record<string, string> = {
  new: "Новый", active: "Активен", suspended: "Приостановлен",
  blocked: "Заблокирован", deleted: "Удалён",
};

const EVENT_LABELS: Record<string, string> = {
  hire: "Приём", transfer: "Перевод", leave_start: "Отпуск",
  leave_end: "Выход из отпуска", terminate: "Увольнение",
};

export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [userRoles, setUserRoles] = useState<UserRole[]>([]);
  const [allRoles, setAllRoles] = useState<Role[]>([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [assigningRole, setAssigningRole] = useState(false);

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const [userResp, eventsResp, rolesResp, allRolesResp] = await Promise.all([
        identityApi.getUser(id),
        identityApi.listEvents({ user_id: id }),
        accessApi.getUserRoles(id),
        accessApi.listRoles({ page_size: 100 }),
      ]);
      setUser(userResp.data);
      setEvents(eventsResp.data.items);
      setUserRoles(rolesResp.data);
      setAllRoles(allRolesResp.data.items);
    } catch {
      setError("Пользователь не найден");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [id]);

  async function doAction(action: "suspend" | "restore" | "block") {
    if (!id) return;
    try {
      if (action === "suspend") await identityApi.suspendUser(id);
      if (action === "restore") await identityApi.restoreUser(id);
      if (action === "block") await identityApi.blockUser(id);
      void load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  async function doResetPassword() {
    if (!id || !newPassword) return;
    setResetting(true);
    try {
      await identityApi.resetPassword(id, newPassword);
      setNewPassword("");
      alert("Пароль сброшен");
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setResetting(false);
    }
  }

  async function doAssignRole() {
    if (!id || !selectedRoleId) return;
    setAssigningRole(true);
    try {
      await accessApi.assignRole(id, { role_id: selectedRoleId });
      setSelectedRoleId("");
      void load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    } finally {
      setAssigningRole(false);
    }
  }

  async function doRevokeRole(userRoleId: string) {
    if (!id) return;
    try {
      await accessApi.revokeRole(id, userRoleId);
      void load();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : String(e));
    }
  }

  if (loading) return <div className="p-6 text-slate-500">Загрузка...</div>;
  if (error || !user) return <div className="p-6 text-red-500">{error || "Не найдено"}</div>;

  const assignedRoleIds = new Set(userRoles.map((ur) => ur.role_id));
  const availableRoles = allRoles.filter((r) => !assignedRoleIds.has(r.id));

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={() => navigate("/identity/users")}>← Назад</Button>
        <h1 className="text-2xl font-bold text-slate-800">{user.full_name}</h1>
        <Badge variant={user.status === "active" ? "default" : user.status === "blocked" ? "destructive" : "secondary"}>
          {STATUS_LABELS[user.status] ?? user.status}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Атрибуты</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Табельный номер" value={user.employee_id} />
            <Row label="Логин" value={user.username} />
            <Row label="Email" value={user.email} />
            <Row label="Должность" value={user.position?.name ?? "—"} />
            <Row label="Отдел" value={user.department?.name ?? "—"} />
            <Row label="LDAP DN" value={user.ldap_dn ?? "не синхронизирован"} />
            <Row label="Создан" value={new Date(user.created_at).toLocaleString("ru-RU")} />
            <Row label="Обновлён" value={new Date(user.updated_at).toLocaleString("ru-RU")} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">Действия</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {user.status === "active" && (
              <div className="flex gap-2 flex-wrap">
                <Button variant="outline" size="sm" onClick={() => doAction("suspend")}>Приостановить</Button>
                <Button variant="destructive" size="sm" onClick={() => doAction("block")}>Заблокировать</Button>
              </div>
            )}
            {user.status === "suspended" && (
              <Button size="sm" onClick={() => doAction("restore")}>Восстановить</Button>
            )}
            <div className="border-t pt-3">
              <p className="text-xs text-slate-500 mb-2">Сброс пароля (LDAP)</p>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder="Новый пароль"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="border rounded px-3 py-1.5 text-sm flex-1"
                />
                <Button size="sm" disabled={resetting || !newPassword} onClick={doResetPassword}>
                  Сбросить
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Роли пользователя */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Роли</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {userRoles.length === 0 ? (
            <p className="text-sm text-slate-400">Роли не назначены</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {userRoles.map((ur) => (
                <div key={ur.id} className="flex items-center gap-1.5 bg-slate-100 rounded-lg px-3 py-1.5">
                  <span className="text-sm font-medium text-slate-700">{ur.role.name}</span>
                  {ur.role.is_privileged && (
                    <Badge variant="destructive" className="text-xs px-1 py-0">привил.</Badge>
                  )}
                  <button
                    onClick={() => doRevokeRole(ur.id)}
                    className="text-slate-400 hover:text-red-500 text-xs ml-1 leading-none"
                    title="Отозвать роль"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {availableRoles.length > 0 && (
            <div className="flex gap-2 pt-1 border-t">
              <select
                value={selectedRoleId}
                onChange={(e) => setSelectedRoleId(e.target.value)}
                className="border rounded px-3 py-1.5 text-sm flex-1 bg-white"
              >
                <option value="">Выбрать роль...</option>
                {availableRoles.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}{r.is_privileged ? " ⚠️" : ""}</option>
                ))}
              </select>
              <Button size="sm" disabled={!selectedRoleId || assigningRole} onClick={doAssignRole}>
                Назначить
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">История кадровых событий</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Событие</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Источник</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Статус</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600">Дата</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {events.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Нет событий</td></tr>
              ) : events.map((ev) => (
                <tr key={ev.id}>
                  <td className="px-4 py-2">{EVENT_LABELS[ev.event_type] ?? ev.event_type}</td>
                  <td className="px-4 py-2 text-slate-500">{ev.source}</td>
                  <td className="px-4 py-2">
                    <Badge variant={ev.status === "processed" ? "default" : ev.status === "failed" ? "destructive" : "secondary"}>
                      {ev.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{new Date(ev.created_at).toLocaleString("ru-RU")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex gap-2">
      <span className="text-slate-500 w-40 shrink-0">{label}:</span>
      <span className="text-slate-800">{value}</span>
    </div>
  );
}
