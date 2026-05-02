import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { accessApi, type Role } from "@/api/access";

export default function Roles() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", description: "", is_privileged: false });
  const [saving, setSaving] = useState(false);

  const pageSize = 20;

  const load = async () => {
    setLoading(true);
    try {
      const res = await accessApi.listRoles({ search: search || undefined, page, page_size: pageSize });
      setRoles(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, search]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await accessApi.createRole(form);
      setShowCreate(false);
      setForm({ code: "", name: "", description: "", is_privileged: false });
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Удалить роль?")) return;
    await accessApi.deleteRole(id);
    load();
  };

  const pages = Math.ceil(total / pageSize);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Роли</h1>
          <p className="text-slate-500 text-sm mt-0.5">Всего: {total}</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
        >
          + Создать роль
        </button>
      </div>

      <input
        type="text"
        placeholder="Поиск по названию или коду..."
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        className="w-full max-w-sm px-3 py-2 border border-slate-200 rounded-lg text-sm"
      />

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <form onSubmit={handleCreate} className="bg-white rounded-xl p-6 w-full max-w-md space-y-4 shadow-xl">
            <h2 className="text-lg font-semibold text-slate-800">Новая роль</h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Код</label>
                <input required className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="my_role" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Название</label>
                <input required className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Описание</label>
                <input className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_privileged} onChange={(e) => setForm({ ...form, is_privileged: e.target.checked })} />
                <span className="text-sm text-slate-700">Привилегированная роль</span>
              </label>
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900">Отмена</button>
              <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">Создать</button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Код</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Название</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Описание</th>
              <th className="px-4 py-3 text-left font-medium text-slate-600">Тип</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Загрузка...</td></tr>
            ) : roles.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">Нет ролей</td></tr>
            ) : roles.map((role) => (
              <tr key={role.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-mono text-xs text-slate-700">{role.code}</td>
                <td className="px-4 py-3 text-slate-800 font-medium">
                  <Link to={`/access/roles/${role.id}`} className="hover:text-blue-600">{role.name}</Link>
                </td>
                <td className="px-4 py-3 text-slate-500 max-w-xs truncate">{role.description}</td>
                <td className="px-4 py-3">
                  {role.is_privileged ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700">Привилегированная</span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">Стандартная</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => handleDelete(role.id)} className="text-xs text-red-500 hover:text-red-700">Удалить</button>
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
