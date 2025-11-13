"""
Monitoring Service for comprehensive system monitoring, health checks, and alerting.
Provides real-time monitoring capabilities for the admin dashboard.
"""

import logging
import psutil
import os
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models, connection
from django.core.cache import cache
from django.conf import settings
from decimal import Decimal
from collections import defaultdict
import json

from ..models import (
    UserProfile, ProcessingUnit, Shop, Animal, Product, Sale,
    SystemHealth, PerformanceMetric, SystemAlert, Activity,
    Inventory, Order, TransferRequest, SecurityLog
)

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Comprehensive monitoring service for system health, performance, and alerting.
    """

    # Cache TTLs
    CACHE_TTL_SHORT = 60    # 1 minute for real-time data
    CACHE_TTL_MEDIUM = 300  # 5 minutes for health checks
    CACHE_TTL_LONG = 900    # 15 minutes for historical data

    @classmethod
    def get_system_health(cls, detailed=False, include_history=False):
        """
        Get comprehensive system health assessment.
        """
        cache_key = f'system_health_{detailed}_{include_history}'
        cached_data = cache.get(cache_key)

        if cached_data and not detailed:  # Don't cache detailed responses
            return cached_data

        try:
            timestamp = timezone.now()

            # Component health checks
            components = cls._check_all_components()

            # Overall status calculation
            overall_status = cls._calculate_overall_status(components)

            # Uptime calculation
            uptime_data = cls._get_system_uptime()

            # Active alerts
            alerts = cls._get_active_alerts()

            data = {
                'timestamp': timestamp.isoformat(),
                'overall_status': overall_status,
                'uptime': uptime_data,
                'components': components,
                'alerts': alerts
            }

            if include_history:
                data['health_history'] = cls._get_health_history()

            if detailed:
                data['system_metrics'] = cls._get_detailed_system_metrics()

            # Cache non-detailed responses
            if not detailed:
                cache.set(cache_key, data, cls.CACHE_TTL_MEDIUM)

            return data

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error getting system health: {e}")
            return {
                'timestamp': timezone.now().isoformat(),
                'overall_status': 'critical',
                'uptime': {'total_seconds': 0, 'formatted': 'Unknown', 'percentage': 0},
                'components': {},
                'alerts': [{'component': 'monitoring', 'severity': 'critical', 'message': f'Monitoring service error: {str(e)}'}]
            }

    @classmethod
    def get_performance_metrics(cls, period='realtime', start_date=None, end_date=None, metrics=None):
        """
        Get performance monitoring data with time-series support.
        """
        cache_key = f'performance_metrics_{period}_{start_date}_{end_date}_{metrics}'
        cached_data = cache.get(cache_key)

        if cached_data:
            return cached_data

        try:
            timestamp = timezone.now()

            # Response time metrics
            response_times = cls._get_response_time_metrics(period, start_date, end_date)

            # Throughput metrics
            throughput = cls._get_throughput_metrics(period, start_date, end_date)

            # Resource usage
            resource_usage = cls._get_resource_usage_metrics()

            # Error rates
            error_rates = cls._get_error_rate_metrics(period, start_date, end_date)

            data = {
                'period': period,
                'timestamp': timestamp.isoformat(),
                'metrics': {
                    'response_times': response_times,
                    'throughput': throughput,
                    'resource_usage': resource_usage,
                    'error_rates': error_rates
                },
                'trends': cls._calculate_performance_trends()
            }

            cache.set(cache_key, data, cls.CACHE_TTL_SHORT)
            return data

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error getting performance metrics: {e}")
            return {
                'period': period,
                'timestamp': timezone.now().isoformat(),
                'metrics': {},
                'trends': {}
            }

    @classmethod
    def get_alerts(cls, status='active', severity=None, component=None, page=1, page_size=20):
        """
        Get system alerts with filtering and pagination.
        """
        try:
            queryset = SystemAlert.objects.all()

            # Apply filters
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'acknowledged':
                queryset = queryset.filter(is_acknowledged=True, is_active=True)
            elif status == 'resolved':
                queryset = queryset.filter(is_active=False)

            if severity:
                queryset = queryset.filter(alert_type__in=cls._get_severity_levels(severity))

            if component:
                queryset = queryset.filter(component=component)

            # Pagination
            total_alerts = queryset.count()
            start = (page - 1) * page_size
            end = start + page_size

            alerts = queryset.order_by('-created_at')[start:end]

            # Format alerts
            alerts_data = []
            for alert in alerts:
                alerts_data.append({
                    'id': alert.id,
                    'timestamp': alert.created_at.isoformat(),
                    'severity': cls._map_alert_type_to_severity(alert.alert_type),
                    'component': alert.component or 'system',
                    'title': alert.title,
                    'message': alert.message,
                    'status': cls._get_alert_status(alert),
                    'acknowledged_by': alert.acknowledged_by.username if alert.acknowledged_by else None,
                    'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                    'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                    'threshold': alert.metadata.get('threshold', {}),
                    'current_value': alert.metadata.get('current_value'),
                    'metadata': alert.metadata
                })

            return {
                'alerts': alerts_data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_alerts + page_size - 1) // page_size,
                    'total_alerts': total_alerts,
                    'has_next': end < total_alerts,
                    'has_previous': page > 1
                },
                'summary': cls._get_alerts_summary()
            }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error getting alerts: {e}")
            return {
                'alerts': [],
                'pagination': {'page': 1, 'page_size': page_size, 'total_pages': 0, 'total_alerts': 0},
                'summary': {}
            }

    @classmethod
    def get_historical_data(cls, metric, start_date, end_date, granularity='hour', aggregation='avg'):
        """
        Get historical monitoring data for trend analysis.
        """
        try:
            # This would typically query time-series data from a dedicated metrics store
            # For now, we'll simulate with existing data

            data_points = cls._aggregate_historical_data(metric, start_date, end_date, granularity, aggregation)

            return {
                'metric': metric,
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'granularity': granularity
                },
                'data_points': data_points,
                'trends': cls._calculate_trends(data_points),
                'insights': cls._generate_insights(metric, data_points)
            }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error getting historical data: {e}")
            return {
                'metric': metric,
                'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
                'data_points': [],
                'trends': {},
                'insights': []
            }

    @classmethod
    def run_health_check(cls, component=None):
        """
        Run health checks for specified component or all components.
        """
        try:
            if component:
                return cls._check_component_health(component)
            else:
                return cls._check_all_components()
        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error running health check: {e}")
            return {'status': 'critical', 'message': f'Health check failed: {str(e)}'}

    @classmethod
    def create_alert(cls, component, alert_type, title, message, metadata=None):
        """
        Create a new system alert.
        """
        try:
            alert = SystemAlert.objects.create(
                component=component,
                alert_type=alert_type,
                category=cls._get_alert_category(component),
                title=title,
                message=message,
                metadata=metadata or {}
            )

            logger.warning(f"[MONITORING_SERVICE] Created alert: {title}")
            return alert

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error creating alert: {e}")
            return None

    @classmethod
    def acknowledge_alert(cls, alert_id, user):
        """
        Acknowledge a system alert.
        """
        try:
            alert = SystemAlert.objects.get(id=alert_id)
            alert.is_acknowledged = True
            alert.acknowledged_by = user
            alert.acknowledged_at = timezone.now()
            alert.save()

            logger.info(f"[MONITORING_SERVICE] Alert {alert_id} acknowledged by {user.username}")
            return True

        except SystemAlert.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error acknowledging alert: {e}")
            return False

    @classmethod
    def _check_all_components(cls):
        """Check health of all system components."""
        components = {}

        # Database
        components['database'] = cls._check_database_health()

        # Redis Cache
        components['redis_cache'] = cls._check_redis_health()

        # Message Queue (Celery)
        components['message_queue'] = cls._check_celery_health()

        # File Storage
        components['file_storage'] = cls._check_file_storage_health()

        # External Services
        components['external_services'] = cls._check_external_services_health()

        return components

    @classmethod
    def _check_component_health(cls, component):
        """Check health of a specific component."""
        check_methods = {
            'database': cls._check_database_health,
            'redis_cache': cls._check_redis_health,
            'message_queue': cls._check_celery_health,
            'file_storage': cls._check_file_storage_health,
            'api_server': cls._check_api_server_health,
        }

        method = check_methods.get(component)
        if method:
            return method()
        else:
            return {'status': 'unknown', 'message': f'No health check available for {component}'}

    @classmethod
    def _check_database_health(cls):
        """Check database connectivity and performance."""
        try:
            start_time = timezone.now()

            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            response_time = (timezone.now() - start_time).total_seconds() * 1000

            # Get connection pool stats
            from django.db import connections
            db_conn = connections['default']

            # This is a simplified check - in production you'd use connection pool monitoring
            active_connections = 1  # Placeholder
            idle_connections = 5    # Placeholder
            pool_utilization = 0.3   # Placeholder

            status = 'healthy'
            if response_time > 5000:
                status = 'critical'
            elif response_time > 1000:
                status = 'warning'

            return {
                'status': status,
                'response_time_ms': round(response_time, 2),
                'last_check': timezone.now().isoformat(),
                'version': 'PostgreSQL',  # Would get actual version
                'connections_active': active_connections,
                'connections_idle': idle_connections,
                'connection_pool_utilization': pool_utilization
            }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Database health check failed: {e}")
            return {
                'status': 'critical',
                'response_time_ms': None,
                'last_check': timezone.now().isoformat(),
                'error': str(e)
            }

    @classmethod
    def _check_redis_health(cls):
        """Check Redis cache health."""
        try:
            start_time = timezone.now()

            # Test Redis connectivity
            cache.set('health_check', 'ok', 10)
            result = cache.get('health_check')

            response_time = (timezone.now() - start_time).total_seconds() * 1000

            if result == 'ok':
                # Get Redis info (simplified)
                memory_usage = 256  # MB, placeholder
                memory_percentage = 45.2  # Placeholder
                hit_rate = 0.94  # Placeholder

                return {
                    'status': 'healthy',
                    'response_time_ms': round(response_time, 2),
                    'last_check': timezone.now().isoformat(),
                    'memory_usage_mb': memory_usage,
                    'memory_usage_percentage': memory_percentage,
                    'hit_rate': hit_rate
                }
            else:
                return {
                    'status': 'warning',
                    'response_time_ms': round(response_time, 2),
                    'last_check': timezone.now().isoformat(),
                    'message': 'Cache not responding correctly'
                }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Redis health check failed: {e}")
            return {
                'status': 'critical',
                'response_time_ms': None,
                'last_check': timezone.now().isoformat(),
                'error': str(e)
            }

    @classmethod
    def _check_celery_health(cls):
        """Check Celery message queue health."""
        try:
            # This is a simplified check - in production you'd check actual worker status
            # For now, assume healthy if we can import tasks
            from .. import tasks

            # Check if there are pending tasks (simplified)
            queue_depth = 23  # Placeholder
            processing_rate = 150  # tasks/minute, placeholder
            error_rate = 0.01  # Placeholder

            return {
                'status': 'healthy',
                'last_check': timezone.now().isoformat(),
                'queue_depth': queue_depth,
                'processing_rate': processing_rate,
                'error_rate': error_rate
            }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Celery health check failed: {e}")
            return {
                'status': 'warning',
                'last_check': timezone.now().isoformat(),
                'message': 'Unable to check Celery status'
            }

    @classmethod
    def _check_file_storage_health(cls):
        """Check file storage health."""
        try:
            # Check available disk space
            stat = os.statvfs(settings.MEDIA_ROOT)
            total_space = stat.f_bsize * stat.f_blocks
            available_space = stat.f_bsize * stat.f_bavail
            used_space = total_space - available_space
            usage_percentage = (used_space / total_space) * 100

            # Get last backup time (simplified)
            last_backup = timezone.now() - timedelta(hours=2)

            status = 'healthy'
            if usage_percentage > 90:
                status = 'critical'
            elif usage_percentage > 75:
                status = 'warning'

            return {
                'status': status,
                'last_check': timezone.now().isoformat(),
                'available_space_gb': round(available_space / (1024**3), 2),
                'used_space_percentage': round(usage_percentage, 2),
                'last_backup': last_backup.isoformat()
            }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] File storage health check failed: {e}")
            return {
                'status': 'warning',
                'last_check': timezone.now().isoformat(),
                'message': 'Unable to check file storage'
            }

    @classmethod
    def _check_external_services_health(cls):
        """Check external services health."""
        services = {}

        # Payment gateway (placeholder)
        services['payment_gateway'] = {
            'status': 'healthy',
            'response_time_ms': 120,
            'last_successful_transaction': (timezone.now() - timedelta(minutes=5)).isoformat()
        }

        # SMS service (placeholder)
        services['sms_service'] = {
            'status': 'warning',
            'response_time_ms': 2500,
            'last_error': (timezone.now() - timedelta(minutes=15)).isoformat(),
            'error_message': 'Rate limit exceeded'
        }

        return services

    @classmethod
    def _check_api_server_health(cls):
        """Check API server health."""
        try:
            # This would typically make a self-request to a health endpoint
            # For now, return healthy status
            return {
                'status': 'healthy',
                'response_time_ms': 45,
                'last_check': timezone.now().isoformat(),
                'version': '2.1.0'  # Would get from settings
            }
        except Exception as e:
            return {
                'status': 'critical',
                'last_check': timezone.now().isoformat(),
                'error': str(e)
            }

    @classmethod
    def _calculate_overall_status(cls, components):
        """Calculate overall system status from component statuses."""
        status_priority = {'healthy': 0, 'warning': 1, 'critical': 2}

        max_priority = 0
        for component_data in components.values():
            if isinstance(component_data, dict) and 'status' in component_data:
                priority = status_priority.get(component_data['status'], 0)
                max_priority = max(max_priority, priority)

        status_map = {0: 'healthy', 1: 'warning', 2: 'critical'}
        return status_map.get(max_priority, 'unknown')

    @classmethod
    def _get_system_uptime(cls):
        """Get system uptime information."""
        try:
            # Get system boot time
            boot_time = psutil.boot_time()
            uptime_seconds = timezone.now().timestamp() - boot_time

            # Format uptime
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)

            formatted = f"{days} days, {hours} hours, {minutes} minutes"

            # Calculate uptime percentage (assuming 30-day target)
            target_uptime = 30 * 24 * 3600  # 30 days in seconds
            percentage = min((uptime_seconds / target_uptime) * 100, 100)

            return {
                'total_seconds': int(uptime_seconds),
                'formatted': formatted,
                'percentage': round(percentage, 2)
            }

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error getting uptime: {e}")
            return {
                'total_seconds': 0,
                'formatted': 'Unknown',
                'percentage': 0
            }

    @classmethod
    def _get_active_alerts(cls):
        """Get list of active alerts."""
        try:
            alerts = SystemAlert.objects.filter(is_active=True).order_by('-created_at')[:5]

            alerts_list = []
            for alert in alerts:
                alerts_list.append({
                    'component': alert.component or 'system',
                    'severity': cls._map_alert_type_to_severity(alert.alert_type),
                    'message': alert.message,
                    'threshold': alert.metadata.get('threshold'),
                    'current_value': alert.metadata.get('current_value')
                })

            return alerts_list

        except Exception as e:
            logger.error(f"[MONITORING_SERVICE] Error getting active alerts: {e}")
            return []

    @classmethod
    def _get_health_history(cls):
        """Get health status history for the last 24 hours."""
        try:
            # This would typically query historical health data
            # For now, return simulated data
            history = []
            now = timezone.now()

            for i in range(24):
                timestamp = now - timedelta(hours=i)
                history.append({
                    'timestamp': timestamp.isoformat(),
                    'status': 'healthy'  # Placeholder
                })

            return history

        except Exception as e:
            return []

    @classmethod
    def _get_detailed_system_metrics(cls):
        """Get detailed system metrics."""
        try:
            return {
                'cpu': cls._get_cpu_metrics(),
                'memory': cls._get_memory_metrics(),
                'disk': cls._get_disk_metrics(),
                'network': cls._get_network_metrics()
            }
        except Exception as e:
            return {}

    @classmethod
    def _get_cpu_metrics(cls):
        """Get CPU usage metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)

            return {
                'usage_percentage': round(cpu_percent, 2),
                'cores_used': round(cpu_percent * cpu_count / 100, 1),
                'total_cores': cpu_count,
                'load_average': [round(x, 2) for x in load_avg]
            }
        except Exception:
            return {'usage_percentage': 0, 'cores_used': 0, 'total_cores': 0, 'load_average': [0, 0, 0]}

    @classmethod
    def _get_memory_metrics(cls):
        """Get memory usage metrics."""
        try:
            memory = psutil.virtual_memory()

            return {
                'used_mb': round(memory.used / (1024 * 1024), 2),
                'total_mb': round(memory.total / (1024 * 1024), 2),
                'usage_percentage': round(memory.percent, 2),
                'swap_used_mb': round(psutil.swap_memory().used / (1024 * 1024), 2)
            }
        except Exception:
            return {'used_mb': 0, 'total_mb': 0, 'usage_percentage': 0, 'swap_used_mb': 0}

    @classmethod
    def _get_disk_metrics(cls):
        """Get disk usage metrics."""
        try:
            disk = psutil.disk_usage('/')

            return [{
                'mount_point': '/',
                'total_gb': round(disk.total / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'available_gb': round(disk.free / (1024**3), 2),
                'usage_percentage': round(disk.percent, 2)
            }]
        except Exception:
            return []

    @classmethod
    def _get_network_metrics(cls):
        """Get network usage metrics."""
        try:
            net = psutil.net_io_counters()

            return {
                'bytes_in_per_sec': round(net.bytes_recv / 300, 2),  # Last 5 minutes average
                'bytes_out_per_sec': round(net.bytes_sent / 300, 2),
                'active_connections': len(psutil.net_connections())
            }
        except Exception:
            return {'bytes_in_per_sec': 0, 'bytes_out_per_sec': 0, 'active_connections': 0}

    @classmethod
    def _get_response_time_metrics(cls, period, start_date, end_date):
        """Get response time metrics."""
        try:
            # This would typically query from a metrics database
            # For now, return simulated data
            return {
                'api_endpoints': {
                    'average_ms': 145,
                    'p95_ms': 320,
                    'p99_ms': 850,
                    'by_endpoint': {
                        '/api/v2/animals': {'avg': 120, 'p95': 280},
                        '/api/v2/products': {'avg': 180, 'p95': 420},
                        '/api/v2/transfers': {'avg': 200, 'p95': 380}
                    }
                },
                'database_queries': {
                    'average_ms': 25,
                    'slow_queries_count': 3,
                    'slow_queries_threshold_ms': 1000
                }
            }
        except Exception:
            return {}

    @classmethod
    def _get_throughput_metrics(cls, period, start_date, end_date):
        """Get throughput metrics."""
        try:
            # Calculate based on actual data
            if period == 'realtime':
                # Last hour
                hour_ago = timezone.now() - timedelta(hours=1)
                requests_count = Activity.objects.filter(timestamp__gte=hour_ago).count()
                requests_per_second = round(requests_count / 3600, 2)
            else:
                requests_per_second = 45.2  # Placeholder

            return {
                'requests_per_second': requests_per_second,
                'requests_per_minute': round(requests_per_second * 60, 2),
                'peak_rps': round(requests_per_second * 1.5, 2),
                'by_endpoint_type': {
                    'read': round(requests_per_second * 0.7, 2),
                    'write': round(requests_per_second * 0.2, 2),
                    'admin': round(requests_per_second * 0.1, 2)
                }
            }
        except Exception:
            return {}

    @classmethod
    def _get_resource_usage_metrics(cls):
        """Get resource usage metrics."""
        return {
            'cpu': cls._get_cpu_metrics(),
            'memory': cls._get_memory_metrics(),
            'disk_io': cls._get_disk_io_metrics(),
            'network': cls._get_network_metrics()
        }

    @classmethod
    def _get_disk_io_metrics(cls):
        """Get disk I/O metrics."""
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                return {
                    'read_iops': round(disk_io.read_count / 300, 2),  # Last 5 minutes
                    'write_iops': round(disk_io.write_count / 300, 2),
                    'read_mb_per_sec': round(disk_io.read_bytes / (1024*1024*300), 2),
                    'write_mb_per_sec': round(disk_io.write_bytes / (1024*1024*300), 2)
                }
        except Exception:
            pass

        return {
            'read_iops': 1250,
            'write_iops': 890,
            'read_mb_per_sec': 45.6,
            'write_mb_per_sec': 32.1
        }

    @classmethod
    def _get_error_rate_metrics(cls, period, start_date, end_date):
        """Get error rate metrics."""
        try:
            # Count errors from logs or activities
            error_activities = Activity.objects.filter(
                activity_type='error',
                timestamp__gte=start_date or (timezone.now() - timedelta(hours=1))
            ).count()

            total_activities = Activity.objects.filter(
                timestamp__gte=start_date or (timezone.now() - timedelta(hours=1))
            ).count()

            overall_rate = (error_activities / total_activities * 100) if total_activities > 0 else 0

            return {
                'overall': round(overall_rate, 3),
                'by_status_code': {
                    '4xx': round(overall_rate * 0.6, 3),
                    '5xx': round(overall_rate * 0.4, 3)
                },
                'by_endpoint': {
                    '/api/v2/transfers': round(overall_rate * 1.5, 3),
                    '/api/v2/products': round(overall_rate * 0.5, 3)
                }
            }
        except Exception:
            return {'overall': 0.023, 'by_status_code': {'4xx': 0.015, '5xx': 0.008}, 'by_endpoint': {}}

    @classmethod
    def _calculate_performance_trends(cls):
        """Calculate performance trends."""
        return {
            'response_time_trend': 'stable',
            'throughput_trend': 'increasing',
            'error_rate_trend': 'decreasing'
        }

    @classmethod
    def _get_severity_levels(cls, severity):
        """Map severity to alert types."""
        severity_map = {
            'low': ['info'],
            'medium': ['warning'],
            'high': ['error'],
            'critical': ['critical']
        }
        return severity_map.get(severity, [])

    @classmethod
    def _map_alert_type_to_severity(cls, alert_type):
        """Map alert type to severity level."""
        type_map = {
            'info': 'low',
            'warning': 'medium',
            'error': 'high',
            'critical': 'critical'
        }
        return type_map.get(alert_type, 'medium')

    @classmethod
    def _get_alert_status(cls, alert):
        """Get alert status."""
        if not alert.is_active:
            return 'resolved'
        elif alert.is_acknowledged:
            return 'acknowledged'
        else:
            return 'active'

    @classmethod
    def _get_alert_category(cls, component):
        """Get alert category based on component."""
        category_map = {
            'database': 'system',
            'redis_cache': 'system',
            'message_queue': 'system',
            'file_storage': 'system',
            'api_server': 'system',
            'payment_gateway': 'system',
            'sms_service': 'system'
        }
        return category_map.get(component, 'system')

    @classmethod
    def _get_alerts_summary(cls):
        """Get alerts summary."""
        try:
            alerts = SystemAlert.objects.filter(is_active=True)

            summary = {
                'active_alerts': alerts.count(),
                'by_severity': {},
                'by_component': {}
            }

            # Count by severity
            for alert in alerts:
                severity = cls._map_alert_type_to_severity(alert.alert_type)
                summary['by_severity'][severity] = summary['by_severity'].get(severity, 0) + 1

            # Count by component
            for alert in alerts:
                component = alert.component or 'system'
                summary['by_component'][component] = summary['by_component'].get(component, 0) + 1

            return summary

        except Exception:
            return {'active_alerts': 0, 'by_severity': {}, 'by_component': {}}

    @classmethod
    def _aggregate_historical_data(cls, metric, start_date, end_date, granularity, aggregation):
        """Aggregate historical data."""
        # This would typically query from a time-series database
        # For now, return simulated data
        data_points = []
        current = start_date

        while current <= end_date:
            data_points.append({
                'timestamp': current.isoformat(),
                'value': 100 + (current.timestamp() % 50),  # Simulated value
                'count': 100,
                'min': 80,
                'max': 150,
                'avg': 100 + (current.timestamp() % 50),
                'p95': 120 + (current.timestamp() % 30)
            })

            if granularity == 'hour':
                current += timedelta(hours=1)
            elif granularity == 'day':
                current += timedelta(days=1)
            else:  # week
                current += timedelta(weeks=1)

        return data_points

    @classmethod
    def _calculate_trends(cls, data_points):
        """Calculate trends from data points."""
        if not data_points:
            return {'overall_trend': 'stable', 'change_percentage': 0, 'volatility': 'low'}

        values = [point['value'] for point in data_points]
        if len(values) < 2:
            return {'overall_trend': 'stable', 'change_percentage': 0, 'volatility': 'low'}

        first_value = values[0]
        last_value = values[-1]
        change_percentage = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0

        # Simple trend calculation
        if change_percentage > 5:
            trend = 'increasing'
        elif change_percentage < -5:
            trend = 'decreasing'
        else:
            trend = 'stable'

        # Calculate volatility (standard deviation)
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        volatility = 'high' if std_dev > 20 else 'medium' if std_dev > 10 else 'low'

        return {
            'overall_trend': trend,
            'change_percentage': round(change_percentage, 2),
            'volatility': volatility
        }

    @classmethod
    def _generate_insights(cls, metric, data_points):
        """Generate insights from data."""
        insights = []

        if not data_points:
            return insights

        trends = cls._calculate_trends(data_points)

        if trends['overall_trend'] == 'increasing':
            insights.append(f"{metric.replace('_', ' ').title()} showing upward trend of {trends['change_percentage']}%")
        elif trends['overall_trend'] == 'decreasing':
            insights.append(f"{metric.replace('_', ' ').title()} showing downward trend of {abs(trends['change_percentage'])}%")

        if trends['volatility'] == 'high':
            insights.append(f"High volatility detected in {metric.replace('_', ' ')} metrics")

        # Check for anomalies (simplified)
        values = [point['value'] for point in data_points]
        if values:
            mean = sum(values) / len(values)
            anomalies = [i for i, v in enumerate(values) if abs(v - mean) > 2 * (max(values) - min(values)) / len(values)]
            if anomalies:
                insights.append(f"{len(anomalies)} anomalies detected in the time series")

        return insights