import { useEffect, useState } from "react";
import { monitorApi, type AlertRule, type AlertSeverity } from "@/api/monitor";

const SEVERITY_BADGE: Record<AlertSeverity, string> = {
  info: "bg-blue-100 text-blue-800",
  low: "bg-zinc-100 text-zinc-800",
  medium: "bg-yellow-100 text-yellow-800",
  high: "bg-orange-100 text-orange-800",
  critical: "bg-red-100 text-red-800",
};

export default function Rules() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [testResults, setTestResults] = useState<Record<string, { matched: boolean; details: Record<string, unknown> }>>({});
  const [testing, setTesting] = useState<string | null>(null);

  const load = async () => {
    const res = await monitorApi.listRules();
    setRules(res.data.items);
  };

  useEffect(() => { load(); }, []);

  const handleToggle = async (rule: AlertRule) => {
    await monitorApi.toggleRule(rule.id);
    load();
  };

  const handleTest = async (rule: AlertRule) => {
    setTesting(rule.id);
    try {
      const res = await monitorApi.testRule(rule.id);
      setTestResults(prev => ({ ...prev, [rule.id]: res.data }));
    } catch {
      setTestResults(prev => ({ ...prev, [rule.id]: { matched: false, details: { error: "Ошибка теста" } } }));
    } finally {
      setTesting(null);
    }
  };

  const simpleRules = rules.filter(r => r.data_source === "postgres");
  const complexRules = rules.filter(r => r.data_source === "elasticsearch");

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Правила выявления</h1>

      <Section title="Простые правила (PostgreSQL)" rules={simpleRules}
        onToggle={handleToggle} onTest={handleTest} testing={testing} testResults={testResults} />

      <Section title="Сложные правила (Elasticsearch)" rules={complexRules}
        onToggle={handleToggle} onTest={handleTest} testing={testing} testResults={testResults} />
    </div>
  );
}

function Section({
  title, rules, onToggle, onTest, testing, testResults,
}: {
  title: string;
  rules: AlertRule[];
  onToggle: (r: AlertRule) => void;
  onTest: (r: AlertRule) => void;
  testing: string | null;
  testResults: Record<string, { matched: boolean; details: Record<string, unknown> }>;
}) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      <div className="space-y-3">
        {rules.map(rule => {
          const testResult = testResults[rule.id];
          return (
            <div key={rule.id}
              className={`bg-white dark:bg-zinc-900 border rounded-lg p-4 ${!rule.is_enabled ? "opacity-60" : ""}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${SEVERITY_BADGE[rule.severity as AlertSeverity]}`}>
                      {rule.severity.toUpperCase()}
                    </span>
                    <span className="font-medium">{rule.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">{rule.code}</span>
                  </div>
                  {rule.description && (
                    <p className="mt-1 text-sm text-muted-foreground">{rule.description}</p>
                  )}
                  <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                    <span>Тип: {rule.condition_type}</span>
                    <span>Cooldown: {rule.cooldown_seconds}с</span>
                    <span>Источник: {rule.data_source}</span>
                  </div>
                  {testResult && (
                    <div className={`mt-2 p-2 rounded text-xs font-mono ${testResult.matched ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
                      {testResult.matched ? "⚠ Сработало" : "✓ Нет срабатываний"}
                      {Object.keys(testResult.details).length > 0 && (
                        <span className="ml-2">{JSON.stringify(testResult.details)}</span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => onTest(rule)}
                    disabled={testing === rule.id}
                    className="px-2 py-1 text-xs border rounded hover:bg-zinc-50 disabled:opacity-40"
                  >
                    {testing === rule.id ? "..." : "Тест"}
                  </button>
                  <button
                    onClick={() => onToggle(rule)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${rule.is_enabled ? "bg-blue-600" : "bg-zinc-300"}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${rule.is_enabled ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
