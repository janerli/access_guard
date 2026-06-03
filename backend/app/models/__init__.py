# Импортируем все модели чтобы SQLAlchemy зарегистрировал их в метадате.
# Без этого FK между таблицами из разных модулей не разрешаются
# (например reports.requested_by → admin_users.id).
from app.models.admin import AdminUser  # noqa: F401
from app.models.identity import (  # noqa: F401
    Position, Department, UserExt, LifecycleEvent,
)
from app.models.access import (  # noqa: F401
    Role, Permission, RolePermission, UserRole,
    Resource, AccessRequest, PositionRoleDefault, ProcessedEvent,
)
from app.models.monitor import (  # noqa: F401
    AuditLog, OutboxEvent, AlertRule, Alert, NotificationChannel,
)
from app.models.reports import Report, ReportTemplate, ReportSchedule  # noqa: F401
