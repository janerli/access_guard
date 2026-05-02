import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { accessApi, type RoleDetail, type Permission } from "@/api/access";

export default function RoleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [role, setRole] = useState<RoleDetail | null>(null);
  const [allPerms, setAllPerms] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", is_privileged: false });
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [roleRes, permsRes] = await Promise.all([
        accessApi.getRole(id),
        accessApi.listPermissions(),
      ]);
      setRole(roleRes.data);
      setAllPerms(permsRes.data);
      setForm({ name: roleRes.data.name, description: roleRes.data.description, is_privileged: roleRes.data.is_privileged });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setSaving(true);
    try {
      await accessApi.updateRole(id, form);
      setEditMode(false);
      load();
    } finally {
      setSaving(false);
    }
  };

  const togglePermission = async (perm: Permission) => {
    if (!id || !role) return;
    const hasIt = role.permissions.some((p) => p.id === perm.id);
    if (hasIt) {
      await accessApi.removePermissionFromRole(id, perm.id);
    } else {
      await accessApi.addPermissionToRole(id, perm.id);
    }
    load();
  };

  if (loading) return <div className="p-6 text-slate-500">Загрузка...</div>;
  if (!role) return <div className="p-6 text-slate-500">Роль не найдена</div>;

  const rolePermIds = new Set(role.permissions.map((p) => p.id));

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <button onClick={() => navigate("/access/roles")} className="text-slate-400 hover:text-slate-700">
          ← Назад
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-800">{role.name}</h1>
          <p className="text-slate-500 text-sm font-mono">{role.code}</p>
        </div>
        <button onClick={() => setEditMode(!editMode)} className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg hover:bg-slate-50">
          {editMode ? "Отмена" : "Редактировать"}
        </button>
      </div>

      {editMode && (
        <form onSubmit={handleSave} className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
          <h2 className="font-medium text-slate-700">Редактирование</h2>
          <div className="grid grid-cols-2 gap-4">
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
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.is_privileged} onChange={(e) => setForm({ ...form, is_privileged: e.target.checked })} />
            <span className="text-sm text-slate-700">Привилегированная роль</span>
          </label>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setEditMode(false)} className="px-4 py-2 text-sm text-slate-600">Отмена</button>
            <button type="submit" disabled={saving} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">Сохранить</button>
          </div>
        </form>
      )}

      {/* Role info */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-slate-500">Описание</dt>
            <dd className="text-slate-800 mt-0.5">{role.description || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Тип</dt>
            <dd className="mt-0.5">
              {role.is_privileged ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700">Привилегированная</span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">Стандартная</span>
              )}
            </dd>
          </div>
        </dl>
      </div>

      {/* Permissions */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200">
          <h2 className="font-medium text-slate-700">Разрешения ({role.permissions.length})</h2>
          <p className="text-xs text-slate-400 mt-0.5">Выберите разрешения для роли</p>
        </div>
        <div className="p-4 grid grid-cols-2 gap-2">
          {allPerms.map((perm) => {
            const active = rolePermIds.has(perm.id);
            return (
              <label key={perm.id} className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 cursor-pointer hover:bg-slate-50">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={() => togglePermission(perm)}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm font-mono text-slate-700">{perm.code}</p>
                  <p className="text-xs text-slate-500">{perm.description}</p>
                </div>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
