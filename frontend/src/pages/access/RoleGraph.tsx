import { useEffect, useState } from "react";
import { accessApi, type RoleDetail } from "@/api/access";

const PRIVILEGE_COLORS = {
  privileged: { bg: "#fee2e2", border: "#ef4444", text: "#991b1b" },
  standard: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
};

export default function RoleGraph() {
  const [roles, setRoles] = useState<RoleDetail[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await accessApi.listRoles({ page_size: 100 });
        // Fetch each role detail to get permissions
        const details = await Promise.all(
          res.data.items.map((r) =>
            accessApi.getRole(r.id).then((d) => d.data as RoleDetail).catch(() => ({ ...r, permissions: [] } as RoleDetail))
          )
        );
        setRoles(details);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const selected = roles.find((r) => r.id === selectedId);

  // Collect all unique permissions across roles
  const allPermissions = Array.from(
    new Map(
      roles.flatMap((r) => (r.permissions ?? []).map((p) => [p.id, p]))
    ).values()
  );

  if (loading) return <div className="p-6 text-slate-500">Загрузка графа...</div>;

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold text-slate-800">Граф ролей и разрешений</h1>
      <p className="text-slate-500 text-sm">
        Кликните на роль, чтобы увидеть её разрешения. Линии показывают связи роль → разрешение.
      </p>

      {roles.length === 0 ? (
        <p className="text-slate-400">Роли не найдены</p>
      ) : (
        <div className="flex gap-6 flex-wrap">
          {/* Roles column */}
          <div className="space-y-2 min-w-[220px]">
            <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">Роли</h2>
            {roles.map((role) => {
              const style = role.is_privileged ? PRIVILEGE_COLORS.privileged : PRIVILEGE_COLORS.standard;
              const isSelected = selectedId === role.id;
              return (
                <button
                  key={role.id}
                  onClick={() => setSelectedId(isSelected ? null : role.id)}
                  className="w-full text-left px-3 py-2 rounded-lg border-2 transition-all text-sm font-medium"
                  style={{
                    backgroundColor: isSelected ? style.border : style.bg,
                    borderColor: style.border,
                    color: isSelected ? "#fff" : style.text,
                  }}
                >
                  {role.name}
                  {role.is_privileged && (
                    <span className="ml-2 text-xs opacity-75">⚠ привил.</span>
                  )}
                  {(role.permissions ?? []).length > 0 && (
                    <span className="ml-1 text-xs opacity-60">({(role.permissions ?? []).length})</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* Arrow */}
          {selected && (
            <div className="flex items-center text-slate-400 text-2xl select-none">→</div>
          )}

          {/* Permissions column */}
          {selected && (
            <div className="space-y-2 min-w-[260px]">
              <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                Разрешения: {selected.name}
              </h2>
              {(selected.permissions ?? []).length === 0 ? (
                <p className="text-slate-400 text-sm">Нет разрешений</p>
              ) : (
                (selected.permissions ?? []).map((perm) => (
                  <div
                    key={perm.id}
                    className="px-3 py-2 rounded-lg border bg-green-50 border-green-200 text-green-800 text-sm"
                  >
                    <span className="font-mono font-semibold">{perm.code}</span>
                    {perm.description && (
                      <p className="text-xs text-green-600 mt-0.5">{perm.description}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* All permissions overview (if nothing selected) */}
          {!selected && allPermissions.length > 0 && (
            <div className="space-y-2 min-w-[260px]">
              <h2 className="text-sm font-semibold text-slate-600 uppercase tracking-wide">
                Все разрешения ({allPermissions.length})
              </h2>
              {allPermissions.map((perm) => (
                <div
                  key={perm.id}
                  className="px-3 py-2 rounded-lg border bg-slate-50 border-slate-200 text-slate-700 text-sm"
                >
                  <span className="font-mono font-semibold">{perm.code}</span>
                  {perm.description && (
                    <p className="text-xs text-slate-500 mt-0.5">{perm.description}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="flex gap-4 pt-4 border-t text-xs text-slate-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded border-2 border-red-500 bg-red-100" />
          Привилегированная роль
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded border-2 border-blue-500 bg-blue-100" />
          Стандартная роль
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded border-2 border-green-500 bg-green-100" />
          Разрешение
        </div>
      </div>
    </div>
  );
}
