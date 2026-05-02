import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { identityApi, type LifecycleEvent, type User } from "@/api/identity";
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [resetting, setResetting] = useState(false);
  const [newPassword, setNewPassword] = useState("");

  async function load() {
    if (!id) return;
    setLoading(true);
    try {
      const [userResp, eventsResp] = await Promise.all([
        identityApi.getUser(id),
        identityApi.listEvents({ user_id: id }),
      ]);
      setUser(userResp.data);
      setEvents(eventsResp.data.items);
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

  if (loading) return <div className="p-6 text-slate-500">Загрузка...</div>;
  if (error || !user) return <div className="p-6 text-red-500">{error || "Не найдено"}</div>;

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
