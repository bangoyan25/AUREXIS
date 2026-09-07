"""AUREXIS database models package.

Importing this package ensures all models are registered with Base.metadata
so that Base.metadata.create_all() creates all tables correctly.
"""

from backend.db.models.account import TradingAccount  # noqa: F401
from backend.db.models.audit_log import AuditLog  # noqa: F401
from backend.db.models.equity import DailySessionState, EquitySnapshot  # noqa: F401
from backend.db.models.execution import ExecutionCommand, ExecutionReport, Position  # noqa: F401
from backend.db.models.mt5_agent import MT5Agent  # noqa: F401
from backend.db.models.news import NewsEvent  # noqa: F401
from backend.db.models.refresh_token import RefreshToken  # noqa: F401
from backend.db.models.risk import RiskConfiguration, RiskDecision  # noqa: F401
from backend.db.models.signal import CandidateSignal  # noqa: F401
from backend.db.models.user import User  # noqa: F401

