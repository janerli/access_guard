import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/auth";

const MODULES = [
  {
    title: "Учётные записи",
    description: "Управление жизненным циклом учётных записей сотрудников, интеграция с LDAP и кадровой системой.",
    to: "/identity",
    color: "bg-blue-500",
    icon: (
      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    title: "Контроль доступа",
    description: "RBAC-модель разграничения прав. Роли, полномочия, матрица доступа, заявки.",
    to: "/access",
    color: "bg-green-500",
    icon: (
      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    title: "Мониторинг",
    description: "Журнал аудита, выявление подозрительной активности, оповещения, дашборды Kibana.",
    to: "/monitor",
    color: "bg-orange-500",
    icon: (
      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    title: "Отчётность",
    description: "8 шаблонов отчётов. PDF, XLSX, CSV. Асинхронная генерация, расписания.",
    to: "/reports",
    color: "bg-purple-500",
    icon: (
      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">
          Добро пожаловать, {user?.full_name?.split(" ")[1] ?? user?.username}
        </h1>
        <p className="text-slate-500 mt-1">
          Система мониторинга и управления доступом к информационным ресурсам
        </p>
      </div>

      {/* Module cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {MODULES.map((mod) => (
          <Card
            key={mod.to}
            className="cursor-pointer hover:shadow-md transition-shadow border-0 shadow-sm"
            onClick={() => navigate(mod.to)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center gap-3">
                <div className={`flex items-center justify-center w-10 h-10 rounded-lg ${mod.color}`}>
                  {mod.icon}
                </div>
                <CardTitle className="text-base">{mod.title}</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-sm leading-relaxed">{mod.description}</CardDescription>
              <Button variant="ghost" size="sm" className="mt-3 -ml-2 text-blue-600 hover:text-blue-700">
                Открыть →
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick links */}
      <div className="mt-6 p-4 bg-slate-100 rounded-xl">
        <h2 className="text-sm font-semibold text-slate-600 mb-3">Внешние интерфейсы</h2>
        <div className="flex flex-wrap gap-3">
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer"
            className="text-sm text-blue-600 hover:underline">
            API Swagger ↗
          </a>
          <a href="http://localhost:5601" target="_blank" rel="noreferrer"
            className="text-sm text-blue-600 hover:underline">
            Kibana ↗
          </a>
          <a href="http://localhost:8025" target="_blank" rel="noreferrer"
            className="text-sm text-blue-600 hover:underline">
            MailHog ↗
          </a>
        </div>
      </div>
    </div>
  );
}
