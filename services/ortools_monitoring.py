#!/usr/bin/env python3
"""
OR-Tools Production Monitoring & Analytics Service
Week 4: Real-time metrics, performance validation, alerting system

Features:
- Real-time performance metrics
- Success/failure rate tracking  
- Performance benchmarking vs legacy
- Alert system for anomalies
- Production health monitoring
"""

import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import statistics
from enum import Enum

# ========================================================================
# 📊 METRICS DATA STRUCTURES
# ========================================================================

class OptimizationStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class OptimizationMetric:
    """Single optimization execution metric"""
    timestamp: datetime
    method: str  # "ortools" or "legacy"
    places_count: int
    days_count: int
    execution_time_ms: int
    status: OptimizationStatus
    city: str
    user_id: Optional[str] = None
    error_message: Optional[str] = None
    distance_calculations: int = 0
    constraints_applied: int = 0
    vehicle_constraints: bool = False
    time_windows: bool = False

@dataclass
class PerformanceWindow:
    """Performance metrics for a time window"""
    start_time: datetime
    end_time: datetime
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    avg_execution_time: float = 0.0
    median_execution_time: float = 0.0
    p95_execution_time: float = 0.0
    ortools_requests: int = 0
    legacy_requests: int = 0
    ortools_success_rate: float = 0.0
    legacy_success_rate: float = 0.0

class ORToolsMonitoring:
    """
    Production monitoring and analytics service for OR-Tools
    Week 4: Real-time metrics, alerts, performance validation
    """
    
    def __init__(self, window_size_minutes: int = 10, max_metrics: int = 10000):
        self.window_size = timedelta(minutes=window_size_minutes)
        self.max_metrics = max_metrics
        
        # Real-time metrics storage (sliding window)
        self.metrics: deque = deque(maxlen=max_metrics)
        self.current_window: PerformanceWindow = self._create_new_window()
        
        # Aggregated statistics
        self.hourly_stats: Dict[str, PerformanceWindow] = {}
        self.daily_stats: Dict[str, PerformanceWindow] = {}
        
        # Alert thresholds
        self.alert_thresholds = {
            'success_rate_threshold': 0.95,  # Alert if success rate < 95%
            'avg_time_threshold': 5000,      # Alert if avg time > 5s
            'p95_time_threshold': 10000,     # Alert if p95 > 10s
            'error_rate_threshold': 0.05     # Alert if error rate > 5%
        }
        
        # Alert state tracking
        self.active_alerts: Dict[str, Dict] = {}
        self.alert_history: List[Dict] = []
        
        # Performance baselines (from benchmarks)
        self.baselines = {
            'ortools': {
                'expected_success_rate': 1.0,
                'expected_avg_time': 2000,
                'expected_p95_time': 4000
            },
            'legacy': {
                'expected_success_rate': 0.0,  # Known to fail
                'expected_avg_time': 8500,
                'expected_p95_time': 15000
            }
        }
        
        logging.info("🔍 OR-Tools Production Monitoring initialized")
        logging.info(f"   Window size: {window_size_minutes} minutes")
        logging.info(f"   Max metrics: {max_metrics:,} entries")
    
    # ====================================================================
    # 📈 METRICS COLLECTION
    # ====================================================================
    
    async def record_optimization(
        self,
        method: str,
        places_count: int,
        days_count: int,
        execution_time_ms: int,
        status: OptimizationStatus,
        city: str,
        user_id: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs
    ) -> None:
        """Record a single optimization execution"""
        
        metric = OptimizationMetric(
            timestamp=datetime.now(),
            method=method,
            places_count=places_count,
            days_count=days_count,
            execution_time_ms=execution_time_ms,
            status=status,
            city=city,
            user_id=user_id,
            error_message=error_message,
            distance_calculations=kwargs.get('distance_calculations', 0),
            constraints_applied=kwargs.get('constraints_applied', 0),
            vehicle_constraints=kwargs.get('vehicle_constraints', False),
            time_windows=kwargs.get('time_windows', False)
        )
        
        # Add to sliding window
        self.metrics.append(metric)
        
        # Update current window
        self._update_current_window(metric)
        
        # Check for window rotation
        await self._check_window_rotation()
        
        # Check for alerts
        await self._check_alerts()
        
        # Log significant events
        if status != OptimizationStatus.SUCCESS:
            logging.warning(f"⚠️ {method} optimization {status.value}: {places_count} places, {execution_time_ms}ms")
            if error_message:
                logging.error(f"   Error: {error_message}")
    
    def _create_new_window(self) -> PerformanceWindow:
        """Create a new performance window"""
        now = datetime.now()
        return PerformanceWindow(
            start_time=now,
            end_time=now + self.window_size
        )
    
    def _update_current_window(self, metric: OptimizationMetric) -> None:
        """Update current window with new metric"""
        window = self.current_window
        window.total_requests += 1
        
        # Update counts by status
        if metric.status == OptimizationStatus.SUCCESS:
            window.success_count += 1
        elif metric.status == OptimizationStatus.FAILURE:
            window.failure_count += 1
        elif metric.status == OptimizationStatus.TIMEOUT:
            window.timeout_count += 1
        elif metric.status == OptimizationStatus.ERROR:
            window.error_count += 1
        
        # Update method counts
        if metric.method == "ortools":
            window.ortools_requests += 1
        else:
            window.legacy_requests += 1
    
    async def _check_window_rotation(self) -> None:
        """Check if we need to rotate to a new window"""
        now = datetime.now()
        if now >= self.current_window.end_time:
            # Finalize current window
            await self._finalize_window(self.current_window)
            
            # Create new window
            self.current_window = self._create_new_window()
            logging.info(f"🔄 Rotated to new monitoring window: {now}")
    
    async def _finalize_window(self, window: PerformanceWindow) -> None:
        """Finalize window calculations"""
        
        # Get metrics for this window
        window_metrics = [
            m for m in self.metrics 
            if window.start_time <= m.timestamp < window.end_time
        ]
        
        if not window_metrics:
            return
        
        # Calculate execution time statistics
        execution_times = [m.execution_time_ms for m in window_metrics]
        window.avg_execution_time = statistics.mean(execution_times)
        window.median_execution_time = statistics.median(execution_times)
        window.p95_execution_time = self._calculate_percentile(execution_times, 0.95)
        
        # Calculate success rates by method
        ortools_metrics = [m for m in window_metrics if m.method == "ortools"]
        legacy_metrics = [m for m in window_metrics if m.method == "legacy"]
        
        if ortools_metrics:
            ortools_successes = len([m for m in ortools_metrics if m.status == OptimizationStatus.SUCCESS])
            window.ortools_success_rate = ortools_successes / len(ortools_metrics)
        
        if legacy_metrics:
            legacy_successes = len([m for m in legacy_metrics if m.status == OptimizationStatus.SUCCESS])
            window.legacy_success_rate = legacy_successes / len(legacy_metrics)
        
        # Store in hourly/daily aggregates
        hour_key = window.start_time.strftime("%Y-%m-%d-%H")
        day_key = window.start_time.strftime("%Y-%m-%d")
        
        self.hourly_stats[hour_key] = window
        if day_key not in self.daily_stats:
            self.daily_stats[day_key] = self._create_daily_aggregate(day_key)
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile value"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        if index >= len(sorted_values):
            index = len(sorted_values) - 1
        return sorted_values[index]
    
    # ====================================================================
    # 🚨 ALERTING SYSTEM
    # ====================================================================
    
    async def _check_alerts(self) -> None:
        """Check for alert conditions"""
        window = self.current_window
        
        if window.total_requests < 5:  # Need minimum data
            return
        
        alerts_to_check = [
            ('success_rate', self._check_success_rate_alert),
            ('avg_execution_time', self._check_avg_time_alert),
            ('p95_execution_time', self._check_p95_time_alert),
            ('error_rate', self._check_error_rate_alert)
        ]
        
        for alert_type, check_func in alerts_to_check:
            alert_data = await check_func(window)
            if alert_data:
                await self._trigger_alert(alert_type, alert_data)
            else:
                await self._clear_alert(alert_type)
    
    async def _check_success_rate_alert(self, window: PerformanceWindow) -> Optional[Dict]:
        """Check success rate alert"""
        success_rate = window.success_count / window.total_requests
        threshold = self.alert_thresholds['success_rate_threshold']
        
        if success_rate < threshold:
            return {
                'current_rate': success_rate,
                'threshold': threshold,
                'failures': window.failure_count,
                'total': window.total_requests,
                'severity': 'HIGH' if success_rate < 0.8 else 'MEDIUM'
            }
        return None
    
    async def _check_avg_time_alert(self, window: PerformanceWindow) -> Optional[Dict]:
        """Check average execution time alert"""
        if window.avg_execution_time > self.alert_thresholds['avg_time_threshold']:
            return {
                'current_time': window.avg_execution_time,
                'threshold': self.alert_thresholds['avg_time_threshold'],
                'severity': 'MEDIUM'
            }
        return None
    
    async def _check_p95_time_alert(self, window: PerformanceWindow) -> Optional[Dict]:
        """Check p95 execution time alert"""
        if window.p95_execution_time > self.alert_thresholds['p95_time_threshold']:
            return {
                'current_time': window.p95_execution_time,
                'threshold': self.alert_thresholds['p95_time_threshold'],
                'severity': 'HIGH'
            }
        return None
    
    async def _check_error_rate_alert(self, window: PerformanceWindow) -> Optional[Dict]:
        """Check error rate alert"""
        error_rate = (window.error_count + window.timeout_count) / window.total_requests
        threshold = self.alert_thresholds['error_rate_threshold']
        
        if error_rate > threshold:
            return {
                'current_rate': error_rate,
                'threshold': threshold,
                'errors': window.error_count,
                'timeouts': window.timeout_count,
                'total': window.total_requests,
                'severity': 'HIGH'
            }
        return None
    
    async def _trigger_alert(self, alert_type: str, alert_data: Dict) -> None:
        """Trigger an alert"""
        alert_id = f"{alert_type}_{datetime.now().isoformat()}"
        
        alert = {
            'id': alert_id,
            'type': alert_type,
            'timestamp': datetime.now(),
            'severity': alert_data.get('severity', 'MEDIUM'),
            'data': alert_data,
            'status': 'ACTIVE'
        }
        
        # Store active alert
        self.active_alerts[alert_type] = alert
        self.alert_history.append(alert)
        
        # Log alert
        severity = alert['severity']
        logging.error(f"🚨 {severity} ALERT: {alert_type}")
        logging.error(f"   Data: {json.dumps(alert_data, indent=2)}")
        
        # Could integrate with external alerting systems here
        # await self._send_to_slack(alert)
        # await self._send_to_pagerduty(alert)
    
    async def _clear_alert(self, alert_type: str) -> None:
        """Clear an active alert"""
        if alert_type in self.active_alerts:
            alert = self.active_alerts[alert_type]
            alert['status'] = 'RESOLVED'
            alert['resolved_at'] = datetime.now()
            
            del self.active_alerts[alert_type]
            logging.info(f"✅ RESOLVED: {alert_type} alert cleared")
    
    # ====================================================================
    # 📊 ANALYTICS & REPORTING
    # ====================================================================
    
    async def get_performance_summary(self, hours: int = 24) -> Dict:
        """Get performance summary for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Filter recent metrics
        recent_metrics = [
            m for m in self.metrics 
            if m.timestamp >= cutoff_time
        ]
        
        if not recent_metrics:
            return {"message": "No metrics available for the specified period"}
        
        # Aggregate statistics
        total_requests = len(recent_metrics)
        successes = len([m for m in recent_metrics if m.status == OptimizationStatus.SUCCESS])
        failures = len([m for m in recent_metrics if m.status == OptimizationStatus.FAILURE])
        timeouts = len([m for m in recent_metrics if m.status == OptimizationStatus.TIMEOUT])
        errors = len([m for m in recent_metrics if m.status == OptimizationStatus.ERROR])
        
        # Method breakdown
        ortools_metrics = [m for m in recent_metrics if m.method == "ortools"]
        legacy_metrics = [m for m in recent_metrics if m.method == "legacy"]
        
        # Execution times
        execution_times = [m.execution_time_ms for m in recent_metrics]
        
        summary = {
            "period": f"Last {hours} hours",
            "timestamp": datetime.now().isoformat(),
            "overview": {
                "total_requests": total_requests,
                "success_rate": successes / total_requests if total_requests > 0 else 0,
                "failure_rate": failures / total_requests if total_requests > 0 else 0,
                "timeout_rate": timeouts / total_requests if total_requests > 0 else 0,
                "error_rate": errors / total_requests if total_requests > 0 else 0
            },
            "performance": {
                "avg_execution_time_ms": statistics.mean(execution_times) if execution_times else 0,
                "median_execution_time_ms": statistics.median(execution_times) if execution_times else 0,
                "p95_execution_time_ms": self._calculate_percentile(execution_times, 0.95),
                "p99_execution_time_ms": self._calculate_percentile(execution_times, 0.99)
            },
            "method_comparison": {
                "ortools": {
                    "requests": len(ortools_metrics),
                    "success_rate": len([m for m in ortools_metrics if m.status == OptimizationStatus.SUCCESS]) / len(ortools_metrics) if ortools_metrics else 0,
                    "avg_time_ms": statistics.mean([m.execution_time_ms for m in ortools_metrics]) if ortools_metrics else 0
                },
                "legacy": {
                    "requests": len(legacy_metrics),
                    "success_rate": len([m for m in legacy_metrics if m.status == OptimizationStatus.SUCCESS]) / len(legacy_metrics) if legacy_metrics else 0,
                    "avg_time_ms": statistics.mean([m.execution_time_ms for m in legacy_metrics]) if legacy_metrics else 0
                }
            },
            "active_alerts": list(self.active_alerts.keys()),
            "alert_count_24h": len([a for a in self.alert_history if a['timestamp'] >= cutoff_time])
        }
        
        return summary
    
    async def get_benchmark_comparison(self) -> Dict:
        """Compare current performance against baselines"""
        summary = await self.get_performance_summary(hours=24)
        
        if not summary or summary.get("overview", {}).get("total_requests", 0) == 0:
            return {"message": "Insufficient data for benchmark comparison"}
        
        ortools_performance = summary["method_comparison"]["ortools"]
        legacy_performance = summary["method_comparison"]["legacy"]
        
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "ortools_analysis": {
                "current_success_rate": ortools_performance["success_rate"],
                "baseline_success_rate": self.baselines["ortools"]["expected_success_rate"],
                "success_rate_delta": ortools_performance["success_rate"] - self.baselines["ortools"]["expected_success_rate"],
                "current_avg_time": ortools_performance["avg_time_ms"],
                "baseline_avg_time": self.baselines["ortools"]["expected_avg_time"],
                "time_performance_ratio": ortools_performance["avg_time_ms"] / self.baselines["ortools"]["expected_avg_time"] if self.baselines["ortools"]["expected_avg_time"] > 0 else 0,
                "status": "MEETING_EXPECTATIONS" if ortools_performance["success_rate"] >= 0.95 and ortools_performance["avg_time_ms"] <= 3000 else "BELOW_EXPECTATIONS"
            },
            "legacy_analysis": {
                "current_success_rate": legacy_performance["success_rate"],  
                "baseline_success_rate": self.baselines["legacy"]["expected_success_rate"],
                "current_avg_time": legacy_performance["avg_time_ms"],
                "baseline_avg_time": self.baselines["legacy"]["expected_avg_time"],
                "status": "AS_EXPECTED" if legacy_performance["success_rate"] <= 0.1 else "UNEXPECTEDLY_WORKING"
            },
            "recommendation": self._generate_recommendation(ortools_performance, legacy_performance)
        }
        
        return comparison
    
    def _generate_recommendation(self, ortools_perf: Dict, legacy_perf: Dict) -> str:
        """Generate performance recommendation"""
        ortools_success = ortools_perf["success_rate"]
        ortools_time = ortools_perf["avg_time_ms"]
        
        if ortools_success >= 0.95 and ortools_time <= 3000:
            return "OR-Tools performing excellently. Continue with current configuration."
        elif ortools_success >= 0.90:
            return "OR-Tools performing well. Monitor execution times for optimization opportunities."
        elif ortools_success >= 0.80:
            return "OR-Tools performance degraded. Check distance cache, parallel optimizer, and OSRM service."
        else:
            return "CRITICAL: OR-Tools performance severely degraded. Immediate investigation required."

# ========================================================================
# 🌐 GLOBAL MONITORING INSTANCE
# ========================================================================

# Global monitoring instance for the application
ortools_monitor = ORToolsMonitoring(window_size_minutes=10)

# ========================================================================
# 🛠️ UTILITY FUNCTIONS
# ========================================================================

async def record_ortools_execution(
    places_count: int,
    days_count: int,
    execution_time_ms: int,
    success: bool,
    city: str,
    user_id: Optional[str] = None,
    error: Optional[str] = None,
    **kwargs
) -> None:
    """Convenience function to record OR-Tools execution"""
    status = OptimizationStatus.SUCCESS if success else OptimizationStatus.FAILURE
    
    await ortools_monitor.record_optimization(
        method="ortools",
        places_count=places_count,
        days_count=days_count,
        execution_time_ms=execution_time_ms,
        status=status,
        city=city,
        user_id=user_id,
        error_message=error,
        **kwargs
    )

async def record_legacy_execution(
    places_count: int,
    days_count: int,
    execution_time_ms: int,
    success: bool,
    city: str,
    user_id: Optional[str] = None,
    error: Optional[str] = None
) -> None:
    """Convenience function to record legacy execution"""
    status = OptimizationStatus.SUCCESS if success else OptimizationStatus.FAILURE
    
    await ortools_monitor.record_optimization(
        method="legacy",
        places_count=places_count,
        days_count=days_count,
        execution_time_ms=execution_time_ms,
        status=status,
        city=city,
        user_id=user_id,
        error_message=error
    )

async def get_monitoring_dashboard() -> Dict:
    """Get comprehensive monitoring dashboard data"""
    return await ortools_monitor.get_performance_summary(hours=24)

async def get_benchmark_report() -> Dict:
    """Get benchmark comparison report"""
    return await ortools_monitor.get_benchmark_comparison()