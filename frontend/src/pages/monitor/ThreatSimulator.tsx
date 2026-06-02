import { useState } from "react";
import { api } from "@/api/client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Scenario {
  code: string;
  name: string;
  description: string;
  severity: string;
  data_source: string;
  how: string;
}

interface SimResult {
  scenario_code: string;
  success: boolean;
  alert_id?: string;
  alert_severity?: string;
  message: string;
  audit_entries_created: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const SEVERITY_STYLE: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border border-red-200",
  high:     "bg-orange-100 text-orange-800 border border-orange-200",
  medium:   "bg-yellow-100 text-yellow-800 border border-yellow-200",
  low:      "bg-blue-100 text-blue-800 border border-blue-200",
  info:     "bg-slate-100 text-slate-600 border border-slate-200",
};

const SEVERITY_LABEL: Record<string, string> = {
  critical: "Критический",
  high:     "Высокий",
  medium:   "Средний",
  low:      "Низкий",
  info:     "Инфо",
};

const SOURCE_LABEL: Record<string, string> = {
  postgres:      "PostgreSQL",
  elasticsearch: "Elasticsearch",
};

const SOURCE_STYLE: Record<string, string> = {
  postgres:      "bg-blue-50 text-blue-700 border border-blue-200",
  elasticsearch: "bg-amber-50 text-amber-700 border border-amber-200",
};

// ── Static scenario list (same as backend, avoids extra fetch) ────────────────

const SCENARIOS: Scenario[] = [
  {
    code: "multiple_failed_logins",
    name: "Множественные неудачные входы",
    description: "5+ неудачных попыток входа за 15 минут от одного пользователя",
    severity: "high",
    data_source: "postgres",
    how: "Создаёт 6 записей login_failure для тестового пользователя и немедленно проверяет правило",
  },
  {
    code: "privileged_role_assigned",
    name: "Назначение привилегированной роли",
    description: "Назначение роли с флагом is_privileged",
    severity: "high",
    data_source: "postgres",
    how: "Создаёт запись role_assign с is_privileged=true и проверяет правило",
  },
  {
    code: "audit_log_tampering_attempt",
    name: "Попытка изменить журнал аудита",
    description: "Попытка UPDATE/DELETE в таблице audit_log",
    severity: "critical",
    data_source: "postgres",
    how: "Создаёт запись delete target_type=system details.table=audit_log",
  },
  {
    code: "admin_password_reset",
    name: "Сброс пароля администратора",
    description: "Сброс пароля пользователя с привилегированной ролью",
    severity: "high",
    data_source: "postgres",
    how: "Создаёт запись password_reset с target_is_privileged=true",
  },
  {
    code: "login_outside_hours",
    name: "Вход в нерабочее время",
    description: "Успешный вход с 22:00 до 06:00",
    severity: "medium",
    data_source: "elasticsearch",
    how: "Создаёт alert напрямую (ES-правило, данные появятся после индексации)",
  },
  {
    code: "mass_permission_failures",
    name: "Массовые отказы в доступе",
    description: "10+ отказов permission_check за 5 минут от одного пользователя",
    severity: "medium",
    data_source: "elasticsearch",
    how: "Создаёт 12 записей permission_check/denied и alert напрямую",
  },
  {
    code: "bulk_user_changes",
    name: "Массовые изменения учётных записей",
    description: "20+ операций изменения за 10 минут от одного администратора",
    severity: "medium",
    data_source: "elasticsearch",
    how: "Создаёт 25 записей операций с пользователями и alert напрямую",
  },
  {
    code: "inactive_user_login",
    name: "Вход под неактивной учётной записью",
    description: "Вход под записью без активности более 90 дней",
    severity: "high",
    data_source: "elasticsearch",
    how: "Создаёт alert напрямую с тестовым неактивным пользователем",
  },
  {
    code: "unusual_geo_login",
    name: "Вход с нового IP-адреса",
    description: "Вход с IP, не встречавшегося в истории последних 30 дней",
    severity: "high",
    data_source: "elasticsearch",
    how: "Создаёт alert напрямую с новыми IP-адресами",
  },
  {
    code: "data_exfiltration_pattern",
    name: "Признаки массовой выгрузки данных",
    description: "157 операций чтения ресурсов за 30 минут",
    severity: "high",
    data_source: "elasticsearch",
    how: "Создаёт alert напрямую с детальной информацией",
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ThreatSimulator() {
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<SimResult[]>([]);
  const [runAllLoading, setRunAllLoading] = useState(false);

  const runScenario = async (code: string) => {
    setLoading((prev) => ({ ...prev, [code]: true }));
    try {
      const { data } = await api.post<SimResult>(`/simulation/run/${code}`);
      setResults((prev) => [data, ...prev]);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Ошибка запроса";
      setResults((prev) => [
        { scenario_code: code, success: false, message: msg, audit_entries_created: 0 },
        ...prev,
      ]);
    } finally {
      setLoading((prev) => ({ ...prev, [code]: false }));
    }
  };

  const runAll = async () => {
    setRunAllLoading(true);
    try {
      const { data } = await api.post<SimResult[]>("/simulation/run-all");
      setResults((prev) => [...data.reverse(), ...prev]);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Ошибка запроса";
      setResults((prev) => [
        { scenario_code: "run-all", success: false, message: msg, audit_entries_created: 0 },
        ...prev,
      ]);
    } finally {
      setRunAllLoading(false);
    }
  };

  const clearResults = () => setResults([]);

  const simpleScenarios = SCENARIOS.filter((s) => s.data_source === "postgres");
  const complexScenarios = SCENARIOS.filter((s) => s.data_source === "elasticsearch");

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Симулятор угроз</h1>
          <p className="text-slate-500 mt-1 text-sm">
            Создаёт синтетические события безопасности для демонстрации работы правил выявления.
            Результаты появляются в{" "}
            <a href="/monitor/alerts" className="text-blue-600 hover:underline">
              Оповещениях
            </a>{" "}
            и{" "}
            <a href="/monitor/audit" className="text-blue-600 hover:underline">
              Журнале аудита
            </a>.
          </p>
        </div>
        <button
          onClick={runAll}
          disabled={runAllLoading}
          className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {runAllLoading ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          )}
          Запустить все (10)
        </button>
      </div>

      {/* Simple rules */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Простые правила
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
            PostgreSQL · срабатывают мгновенно
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {simpleScenarios.map((s) => (
            <ScenarioCard
              key={s.code}
              scenario={s}
              loading={!!loading[s.code]}
              result={results.find((r) => r.scenario_code === s.code)}
              onRun={() => runScenario(s.code)}
            />
          ))}
        </div>
      </section>

      {/* Complex rules */}
      <section>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Сложные правила
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
            Elasticsearch · alert создаётся напрямую
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {complexScenarios.map((s) => (
            <ScenarioCard
              key={s.code}
              scenario={s}
              loading={!!loading[s.code]}
              result={results.find((r) => r.scenario_code === s.code)}
              onRun={() => runScenario(s.code)}
            />
          ))}
        </div>
      </section>

      {/* Results log */}
      {results.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Лента результатов ({results.length})
            </span>
            <button
              onClick={clearResults}
              className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
            >
              Очистить
            </button>
          </div>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {results.map((r, i) => (
              <ResultRow key={i} result={r} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ScenarioCard({
  scenario,
  loading,
  result,
  onRun,
}: {
  scenario: Scenario;
  loading: boolean;
  result?: SimResult;
  onRun: () => void;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 hover:border-slate-300 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_STYLE[scenario.severity] ?? ""}`}
            >
              {SEVERITY_LABEL[scenario.severity] ?? scenario.severity}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${SOURCE_STYLE[scenario.data_source] ?? ""}`}
            >
              {SOURCE_LABEL[scenario.data_source] ?? scenario.data_source}
            </span>
          </div>
          <p className="text-sm font-semibold text-slate-800 mt-1">{scenario.name}</p>
          <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{scenario.description}</p>
          <p className="text-xs text-slate-400 mt-1 italic">{scenario.how}</p>
        </div>
        <button
          onClick={onRun}
          disabled={loading}
          className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 text-white text-xs font-medium rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          Запустить
        </button>
      </div>

      {/* Last result badge */}
      {result && (
        <div
          className={`mt-3 flex items-start gap-2 text-xs rounded-lg px-3 py-2 ${
            result.success
              ? "bg-green-50 text-green-800 border border-green-200"
              : "bg-red-50 text-red-800 border border-red-200"
          }`}
        >
          <span className="mt-0.5 shrink-0">
            {result.success ? "✓" : "✗"}
          </span>
          <span className="leading-relaxed">
            {result.message}
            {result.alert_id && (
              <span className="ml-1 font-mono opacity-60">
                #{result.alert_id.slice(0, 8)}
              </span>
            )}
          </span>
        </div>
      )}
    </div>
  );
}

function ResultRow({ result }: { result: SimResult }) {
  const scenario = SCENARIOS.find((s) => s.code === result.scenario_code);
  const ts = new Date().toLocaleTimeString("ru-RU");

  return (
    <div
      className={`flex items-start gap-3 text-sm rounded-lg px-4 py-3 ${
        result.success
          ? "bg-green-50 border border-green-200"
          : "bg-red-50 border border-red-200"
      }`}
    >
      <span className={`mt-0.5 font-bold text-base ${result.success ? "text-green-600" : "text-red-500"}`}>
        {result.success ? "✓" : "✗"}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-800">
            {scenario?.name ?? result.scenario_code}
          </span>
          {result.alert_severity && (
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_STYLE[result.alert_severity] ?? ""}`}
            >
              {SEVERITY_LABEL[result.alert_severity] ?? result.alert_severity}
            </span>
          )}
          <span className="ml-auto text-xs text-slate-400 shrink-0">{ts}</span>
        </div>
        <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{result.message}</p>
        {result.audit_entries_created > 0 && (
          <p className="text-xs text-slate-400 mt-0.5">
            Создано записей аудита: {result.audit_entries_created}
          </p>
        )}
      </div>
    </div>
  );
}
