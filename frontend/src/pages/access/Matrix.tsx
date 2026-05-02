import { useEffect, useState } from "react";
import { accessApi, type PositionMatrixRow, type Role } from "@/api/access";

export default function Matrix() {
  const [matrix, setMatrix] = useState<PositionMatrixRow[]>([]);
  const [allRoles, setAllRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const [matrixRes, rolesRes] = await Promise.all([
        accessApi.getMatrix(),
        accessApi.listRoles({ page_size: 100 }),
      ]);
      setMatrix(matrixRes.data);
      setAllRoles(rolesRes.data.items);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggleDefault = async (positionId: string, roleId: string, currentRoleIds: string[]) => {
    setSaving(positionId);
    try {
      const hasIt = currentRoleIds.includes(roleId);
      const newIds = hasIt ? currentRoleIds.filter((id) => id !== roleId) : [...currentRoleIds, roleId];
      await accessApi.updateMatrix(positionId, newIds);
      load();
    } finally {
      setSaving(null);
    }
  };

  if (loading) return <div className="p-6 text-slate-500">Загрузка...</div>;

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Матрица доступа</h1>
        <p className="text-slate-500 text-sm mt-0.5">Роли по умолчанию для каждой должности</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-slate-600 min-w-48">Должность</th>
              {allRoles.map((role) => (
                <th key={role.id} className="px-3 py-3 text-center font-medium text-slate-600 whitespace-nowrap">
                  <span className="font-mono text-xs">{role.code}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {matrix.map((row) => (
              <tr key={row.position_id} className={saving === row.position_id ? "opacity-50" : "hover:bg-slate-50"}>
                <td className="px-4 py-3">
                  <p className="font-medium text-slate-800">{row.position_name}</p>
                  <p className="text-xs font-mono text-slate-500">{row.position_code}</p>
                </td>
                {allRoles.map((role) => {
                  const active = row.role_ids.includes(role.id);
                  return (
                    <td key={role.id} className="px-3 py-3 text-center">
                      <button
                        onClick={() => toggleDefault(row.position_id, role.id, row.role_ids)}
                        disabled={saving === row.position_id}
                        className={`w-6 h-6 rounded border transition-colors ${
                          active
                            ? "bg-blue-600 border-blue-600 text-white"
                            : "border-slate-200 hover:border-blue-300 text-transparent"
                        }`}
                        title={active ? "Удалить связь" : "Добавить связь"}
                      >
                        ✓
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
