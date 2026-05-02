import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { identityApi, type Department, type Position, type User, type UserStatus } from "@/api/identity";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STATUS_LABELS: Record<UserStatus, string> = {
  new: "Новый",
  active: "Активен",
  suspended: "Приостановлен",
  blocked: "Заблокирован",
  deleted: "Удалён",
};

const STATUS_VARIANT: Record<UserStatus, "default" | "secondary" | "destructive" | "outline"> = {
  new: "secondary",
  active: "default",
  suspended: "outline",
  blocked: "destructive",
  deleted: "destructive",
};

export default function Users() {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [positions, setPositions] = useState<Position[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);

  const PAGE_SIZE = 20;

  async function load() {
    setLoading(true);
    setError("");
    try {
      const resp = await identityApi.listUsers({
        search: search || undefined,
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
      });
      setUsers(resp.data.items);
      setTotal(resp.data.total);
    } catch {
      setError("Ошибка загрузки списка пользователей");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [page, statusFilter]);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter]);

  useEffect(() => {
    identityApi.listPositions().then((r) => setPositions(r.data));
    identityApi.listDepartments().then((r) => setDepartments(r.data));
  }, []);

  async function handleAction(action: "suspend" | "restore" | "block", userId: string) {
    try {
      if (action === "suspend") await identityApi.suspendUser(userId);
      if (action === "restore") await identityApi.restoreUser(userId);
      if (action === "block") await identityApi.blockUser(userId);
      void load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert(`Ошибка: ${msg}`);
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Пользователи</h1>
        <Button onClick={() => setShowCreate(true)}>+ Создать</Button>
      </div>

      {showCreate && (
        <CreateUserForm
          positions={positions}
          departments={departments}
          onCreated={() => { setShowCreate(false); void load(); }}
          onCancel={() => setShowCreate(false)}
        />
      )}

      <div className="flex gap-3">
        <Input
          placeholder="Поиск по имени, логину, email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
          className="max-w-xs"
        />
        <select
          className="border rounded px-3 py-2 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">Все статусы</option>
          {Object.entries(STATUS_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <Button variant="outline" onClick={load}>Найти</Button>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-medium text-slate-600">
            Всего: {total}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">ФИО</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Логин</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Email</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Отдел</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Статус</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Загрузка...</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Нет данных</td></tr>
                ) : users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link to={`/identity/users/${u.id}`} className="font-medium text-blue-600 hover:underline">
                        {u.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{u.username}</td>
                    <td className="px-4 py-3 text-slate-600">{u.email}</td>
                    <td className="px-4 py-3 text-slate-500">{u.department?.name ?? "—"}</td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[u.status]}>{STATUS_LABELS[u.status]}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1">
                        {u.status === "active" && (
                          <>
                            <Button size="sm" variant="outline" onClick={() => handleAction("suspend", u.id)}>
                              Приостановить
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => handleAction("block", u.id)}>
                              Заблокировать
                            </Button>
                          </>
                        )}
                        {u.status === "suspended" && (
                          <Button size="sm" variant="outline" onClick={() => handleAction("restore", u.id)}>
                            Восстановить
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex gap-2 justify-center">
          <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
            ←
          </Button>
          <span className="text-sm text-slate-600 self-center">
            {page} / {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>
            →
          </Button>
        </div>
      )}
    </div>
  );
}

function CreateUserForm({
  positions,
  departments,
  onCreated,
  onCancel,
}: {
  positions: Position[];
  departments: Department[];
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({
    employee_id: "",
    username: "",
    email: "",
    full_name: "",
    position_code: "",
    department_code: "",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      await identityApi.createUser({
        ...form,
        position_code: form.position_code || undefined,
        department_code: form.department_code || undefined,
      });
      onCreated();
    } catch (ex: unknown) {
      const msg = ex instanceof Error ? ex.message : "Ошибка создания";
      setErr(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="border-blue-200">
      <CardHeader>
        <CardTitle className="text-base">Новый пользователь</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="grid grid-cols-2 gap-3">
          <Input placeholder="Табельный номер (E-1234)" value={form.employee_id} onChange={e => setForm(f => ({...f, employee_id: e.target.value}))} required />
          <Input placeholder="Логин" value={form.username} onChange={e => setForm(f => ({...f, username: e.target.value}))} required />
          <Input placeholder="Email" type="email" value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))} required />
          <Input placeholder="ФИО" value={form.full_name} onChange={e => setForm(f => ({...f, full_name: e.target.value}))} required />
          <select className="border rounded px-3 py-2 text-sm" value={form.position_code} onChange={e => setForm(f => ({...f, position_code: e.target.value}))}>
            <option value="">Должность (опционально)</option>
            {positions.map(p => <option key={p.id} value={p.code}>{p.name}</option>)}
          </select>
          <select className="border rounded px-3 py-2 text-sm" value={form.department_code} onChange={e => setForm(f => ({...f, department_code: e.target.value}))}>
            <option value="">Отдел (опционально)</option>
            {departments.map(d => <option key={d.id} value={d.code}>{d.name}</option>)}
          </select>
          {err && <p className="col-span-2 text-red-500 text-sm">{err}</p>}
          <div className="col-span-2 flex gap-2">
            <Button type="submit" disabled={saving}>{saving ? "Сохранение..." : "Создать"}</Button>
            <Button type="button" variant="outline" onClick={onCancel}>Отмена</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
