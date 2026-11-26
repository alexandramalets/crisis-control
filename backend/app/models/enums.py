from enum import StrEnum


class ImpactDirection(StrEnum):
    """Как рост показателя влияет на состояние организации (ПЗ, с. 22)."""

    HIGHER_IS_BETTER = "higher_better"
    LOWER_IS_BETTER = "lower_better"
    NEUTRAL = "neutral"


class PeriodGranularity(StrEnum):
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class IssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class TargetKind(StrEnum):
    PLAN = "plan"
    NORM = "norm"
    TARGET = "target"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"


class ProcedureType(StrEnum):
    PREPROCESSING = "preprocessing"
    ANOMALIES = "anomalies"
    TRENDS = "trends"
    CORRELATION = "correlation"
    CLUSTERING = "clustering"
    FORECASTING = "forecasting"
    ASSESSMENT = "assessment"
    RATIOS = "ratios"


class ProcedureStatus(StrEnum):
    PENDING = "pending"
    OK = "ok"
    SKIPPED = "skipped"
    ERROR = "error"


class PreprocessingActionType(StrEnum):
    IMPUTED = "imputed"
    EXCLUDED = "excluded"


class ReportFormat(StrEnum):
    PDF = "pdf"
    XLSX = "xlsx"


class ReportStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class OrganizationAccessLevel(StrEnum):
    VIEW = "view"
    EDIT = "edit"
