import { useState } from "react";
import { useAuthStore } from "@/store/auth";
import { authApi } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const ROLE_LABELS: Record<string, string> = {
  system_admin: "Системный администратор",
  security_officer: "Офицер безопасности",
  hr_operator: "HR-оператор",
  auditor: "Аудитор",
};

export default function Profile() {
  const { user } = useAuthStore();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  const showToast = (type: "success" | "error", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const validate = (): string | null => {
    if (!currentPassword) return "Введите текущий пароль";
    if (newPassword.length < 12) return "Новый пароль должен содержать не менее 12 символов";
    if (newPassword === currentPassword) return "Новый пароль должен отличаться от текущего";
    if (newPassword !== confirmPassword) return "Пароли не совпадают";
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate();
    if (err) { showToast("error", err); return; }
    setSaving(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      showToast("success", "Пароль успешно изменён");
    } catch (ex: unknown) {
      const msg =
        (ex as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Ошибка при смене пароля";
      showToast("error", msg);
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">Профиль администратора</h1>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-lg shadow-lg text-white text-sm font-medium transition-all
            ${toast.type === "success" ? "bg-green-600" : "bg-red-600"}`}
        >
          {toast.msg}
        </div>
      )}

      {/* Info card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Информация об аккаунте</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex gap-2 items-center">
            <span className="text-slate-500 w-36 shrink-0">Полное имя:</span>
            <span className="font-medium text-slate-800">{user.full_name}</span>
          </div>
          <div className="flex gap-2 items-center">
            <span className="text-slate-500 w-36 shrink-0">Логин:</span>
            <span className="font-mono text-slate-800">{user.username}</span>
          </div>
          <div className="flex gap-2 items-center">
            <span className="text-slate-500 w-36 shrink-0">Email:</span>
            <span className="text-slate-800">{user.email}</span>
          </div>
          <div className="flex gap-2 items-center">
            <span className="text-slate-500 w-36 shrink-0">Роль:</span>
            <Badge variant="secondary">{ROLE_LABELS[user.role] ?? user.role}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Change password card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Изменить пароль</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Текущий пароль</label>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Введите текущий пароль"
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Новый пароль (мин. 12 символов)</label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Введите новый пароль"
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">Подтвердите новый пароль</label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Повторите новый пароль"
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? "Сохранение..." : "Изменить пароль"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
