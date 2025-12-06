"""
Error Logger for Sovereign V5 Self-Improvement

Logs evaluation errors for pattern analysis and prompt refinement.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class ErrorLog:
    """Single error log entry."""
    error_id: str
    timestamp: str
    judge_id: str
    framework: str
    test_case_id: str
    error_type: str  # false_positive, false_negative, low_confidence, exception
    expected_outcome: bool
    actual_outcome: bool
    expected_severity: Optional[str]
    actual_severity: Optional[str]
    submission_text: str
    error_details: Optional[str]
    confidence: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ErrorLogger:
    """
    Logs judge evaluation errors for analysis.

    Stores errors in JSON file for pattern analysis and prompt refinement.
    """

    def __init__(self, log_path: str = "data/error_logs.json"):
        """
        Initialize error logger.

        Args:
            log_path: Path to error log JSON file.
        """
        self.log_path = Path(log_path)
        self._lock = Lock()
        self._ensure_log_file()

    def _ensure_log_file(self):
        """Ensure log file and directory exist."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("[]")
            logger.info(f"Created error log file at {self.log_path}")

    def log_error(
        self,
        judge_id: str,
        framework: str,
        test_case_id: str,
        error_type: str,
        expected_outcome: bool,
        actual_outcome: bool,
        submission_text: str,
        expected_severity: Optional[str] = None,
        actual_severity: Optional[str] = None,
        error_details: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> str:
        """
        Log an evaluation error.

        Args:
            judge_id: Judge that made the error.
            framework: Framework being evaluated.
            test_case_id: Test case identifier.
            error_type: Type of error (false_positive, false_negative, etc).
            expected_outcome: Expected violation flag.
            actual_outcome: Actual violation flag.
            submission_text: Submission that caused error.
            expected_severity: Expected severity level.
            actual_severity: Actual severity level.
            error_details: Additional error details.
            confidence: Confidence score if available.

        Returns:
            Error ID.
        """
        with self._lock:
            # Generate error ID
            error_id = f"{judge_id}_{test_case_id}_{datetime.utcnow().timestamp()}"

            # Create error log entry
            error_log = ErrorLog(
                error_id=error_id,
                timestamp=datetime.utcnow().isoformat(),
                judge_id=judge_id,
                framework=framework,
                test_case_id=test_case_id,
                error_type=error_type,
                expected_outcome=expected_outcome,
                actual_outcome=actual_outcome,
                expected_severity=expected_severity,
                actual_severity=actual_severity,
                submission_text=submission_text,
                error_details=error_details,
                confidence=confidence
            )

            # Load existing logs
            try:
                with open(self.log_path, 'r') as f:
                    logs = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load error logs: {e}")
                logs = []

            # Append new log
            logs.append(error_log.to_dict())

            # Save back to file
            try:
                with open(self.log_path, 'w') as f:
                    json.dump(logs, f, indent=2)
                logger.info(f"Logged error {error_id} for {judge_id}")
            except Exception as e:
                logger.error(f"Failed to save error log: {e}")

            return error_id

    def get_errors(
        self,
        judge_id: Optional[str] = None,
        framework: Optional[str] = None,
        error_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve error logs with optional filtering.

        Args:
            judge_id: Filter by judge ID.
            framework: Filter by framework.
            error_type: Filter by error type.
            limit: Maximum number of errors to return.

        Returns:
            List of error log dictionaries.
        """
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    logs = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load error logs: {e}")
                return []

            # Apply filters
            filtered = logs

            if judge_id:
                filtered = [log for log in filtered if log.get('judge_id') == judge_id]

            if framework:
                filtered = [log for log in filtered if log.get('framework') == framework]

            if error_type:
                filtered = [log for log in filtered if log.get('error_type') == error_type]

            # Apply limit
            if limit:
                filtered = filtered[-limit:]

            return filtered

    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of logged errors.

        Returns:
            Dictionary with error statistics.
        """
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    logs = json.load(f)
            except Exception:
                return {
                    "total_errors": 0,
                    "error_types": {},
                    "errors_by_judge": {},
                    "errors_by_framework": {}
                }

            # Calculate statistics
            error_types = {}
            errors_by_judge = {}
            errors_by_framework = {}

            for log in logs:
                # Count by error type
                error_type = log.get('error_type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1

                # Count by judge
                judge_id = log.get('judge_id', 'unknown')
                errors_by_judge[judge_id] = errors_by_judge.get(judge_id, 0) + 1

                # Count by framework
                framework = log.get('framework', 'unknown')
                errors_by_framework[framework] = errors_by_framework.get(framework, 0) + 1

            return {
                "total_errors": len(logs),
                "error_types": error_types,
                "errors_by_judge": errors_by_judge,
                "errors_by_framework": errors_by_framework
            }

    def clear_errors(
        self,
        judge_id: Optional[str] = None,
        before_timestamp: Optional[str] = None
    ):
        """
        Clear error logs with optional filtering.

        Args:
            judge_id: Clear errors for specific judge.
            before_timestamp: Clear errors before timestamp.
        """
        with self._lock:
            try:
                with open(self.log_path, 'r') as f:
                    logs = json.load(f)

                # Filter logs to keep
                if judge_id:
                    logs = [log for log in logs if log.get('judge_id') != judge_id]

                if before_timestamp:
                    logs = [
                        log for log in logs
                        if log.get('timestamp', '') >= before_timestamp
                    ]

                # Save filtered logs
                with open(self.log_path, 'w') as f:
                    json.dump(logs, f, indent=2)

                logger.info("Cleared error logs")

            except Exception as e:
                logger.error(f"Failed to clear error logs: {e}")


# Global singleton
_logger_instance: Optional[ErrorLogger] = None
_logger_lock = Lock()


def get_error_logger() -> ErrorLogger:
    """
    Get global ErrorLogger singleton.

    Returns:
        ErrorLogger instance.
    """
    global _logger_instance

    if _logger_instance is None:
        with _logger_lock:
            if _logger_instance is None:
                _logger_instance = ErrorLogger()
                logger.info("Created global ErrorLogger instance")

    return _logger_instance
