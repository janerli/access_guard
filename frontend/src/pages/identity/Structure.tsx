import { useEffect, useState } from "react";
import { identityApi, type Department, type Position } from "@/api/identity";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Structure() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([identityApi.listDepartments(), identityApi.listPositions()])
      .then(([dResp, pResp]) => {
        setDepartments(dResp.data);
        setPositions(pResp.data);
      })
      .finally(() => setLoading(false));
  }, []);

  const roots = departments.filter((d) => !d.parent_id);

  function renderDept(dept: Department, depth = 0): React.ReactNode {
    const children = departments.filter((d) => d.parent_id === dept.id);
    return (
      <div key={dept.id} style={{ marginLeft: depth * 20 }}>
        <div className="flex items-center gap-2 py-1">
          <span className="text-slate-400 select-none">{depth > 0 ? "└─" : "•"}</span>
          <span className="font-medium text-slate-800">{dept.name}</span>
          <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded">{dept.code}</span>
        </div>
        {children.map((c) => renderDept(c, depth + 1))}
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-bold text-slate-800">Оргструктура</h1>

      {loading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Отделы</CardTitle></CardHeader>
            <CardContent className="text-sm">
              {departments.length === 0 ? (
                <p className="text-slate-400">Нет отделов</p>
              ) : (
                roots.map((r) => renderDept(r))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle className="text-base">Должности</CardTitle></CardHeader>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-2 font-medium text-slate-600">Название</th>
                    <th className="text-left px-4 py-2 font-medium text-slate-600">Код</th>
                    <th className="text-left px-4 py-2 font-medium text-slate-600">Уровень</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {positions.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50">
                      <td className="px-4 py-2">{p.name}</td>
                      <td className="px-4 py-2 text-slate-500 font-mono text-xs">{p.code}</td>
                      <td className="px-4 py-2 text-slate-500">{p.level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
