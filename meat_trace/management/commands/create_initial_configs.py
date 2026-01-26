from django.core.management.base import BaseCommand
from django.utils import timezone
from meat_trace.models import SystemConfiguration, FeatureFlag


class Command(BaseCommand):
    help = 'Create initial system configurations and feature flags'

    def handle(self, *args, **options):
        self.stdout.write('Creating initial system configurations...')

        # System configurations
        configs = [
            {
                'key': 'database.connection_pool.max_size',
                'value': '50',
                'default_value': '20',
                'data_type': 'integer',
                'category': 'database',
                'environment': 'production',
                'description': 'Maximum database connection pool size',
                'validation_rules': {'min': 1, 'max': 1000, 'required': True},
                'requires_restart': True,
                'tags': ['database', 'performance', 'connection']
            },
            {
                'key': 'cache.redis.ttl_seconds',
                'value': '3600',
                'default_value': '1800',
                'data_type': 'integer',
                'category': 'cache',
                'environment': 'production',
                'description': 'Redis cache TTL in seconds',
                'validation_rules': {'min': 60, 'max': 86400, 'required': True},
                'tags': ['cache', 'redis', 'performance']
            },
            {
                'key': 'api.rate_limit.requests_per_hour',
                'value': '10000',
                'default_value': '5000',
                'data_type': 'integer',
                'category': 'api',
                'environment': 'production',
                'description': 'API rate limit requests per hour',
                'validation_rules': {'min': 100, 'max': 100000, 'required': True},
                'tags': ['api', 'rate-limiting', 'performance']
            },
            {
                'key': 'logging.level',
                'value': 'INFO',
                'default_value': 'WARNING',
                'data_type': 'string',
                'category': 'logging',
                'environment': 'production',
                'description': 'Application logging level',
                'validation_rules': {'required': True},
                'tags': ['logging', 'monitoring']
            },
            {
                'key': 'notification.email.enabled',
                'value': 'true',
                'default_value': 'false',
                'data_type': 'boolean',
                'category': 'notification',
                'environment': 'production',
                'description': 'Enable email notifications',
                'validation_rules': {'required': True},
                'tags': ['notification', 'email']
            }
        ]

        for config_data in configs:
            config, created = SystemConfiguration.objects.get_or_create(
                key=config_data['key'],
                defaults=config_data
            )
            if created:
                self.stdout.write(f'  Created config: {config.key}')
            else:
                self.stdout.write(f'  Config already exists: {config.key}')

        # Feature flags
        self.stdout.write('Creating initial feature flags...')

        flags = [
            {
                'name': 'Enhanced QR Code Tracking',
                'key': 'feature_qr_enhanced_tracking',
                'description': 'Advanced QR code scanning with real-time validation',
                'status': 'enabled',
                'environment': 'production',
                'target_audience': {
                    'type': 'percentage',
                    'percentage': 100,
                    'user_segments': ['abbatoirs', 'processors'],
                    'excluded_users': []
                },
                'rollout_schedule': {
                    'start_date': '2025-11-01T00:00:00Z',
                    'end_date': None,
                    'gradual_rollout': False
                },
                'kill_switch_enabled': True,
                'monitoring_enabled': True,
                'dependencies': ['feature_basic_qr'],
                'tags': ['qr', 'tracking', 'mobile']
            },
            {
                'name': 'Advanced Analytics Dashboard',
                'key': 'feature_advanced_analytics',
                'description': 'New analytics dashboard with predictive insights',
                'status': 'disabled',
                'environment': 'staging',
                'target_audience': {
                    'type': 'user_list',
                    'user_ids': [],
                    'user_segments': ['admins']
                },
                'rollout_schedule': {
                    'start_date': '2025-11-15T00:00:00Z',
                    'gradual_rollout': True,
                    'rollout_percentage_per_day': 10
                },
                'kill_switch_enabled': True,
                'monitoring_enabled': True,
                'dependencies': ['feature_basic_analytics'],
                'tags': ['analytics', 'dashboard', 'predictive']
            },
            {
                'name': 'Automated Quality Checks',
                'key': 'feature_auto_quality_checks',
                'description': 'Automated quality validation for animal and product submissions',
                'status': 'scheduled',
                'environment': 'production',
                'target_audience': {
                    'type': 'all_users'
                },
                'rollout_schedule': {
                    'start_date': '2025-12-01T00:00:00Z',
                    'gradual_rollout': True,
                    'rollout_percentage_per_day': 5
                },
                'kill_switch_enabled': True,
                'monitoring_enabled': True,
                'dependencies': [],
                'tags': ['quality', 'automation', 'validation']
            }
        ]

        for flag_data in flags:
            flag, created = FeatureFlag.objects.get_or_create(
                key=flag_data['key'],
                defaults=flag_data
            )
            if created:
                self.stdout.write(f'  Created feature flag: {flag.name}')
            else:
                self.stdout.write(f'  Feature flag already exists: {flag.name}')

        self.stdout.write(self.style.SUCCESS('Successfully created initial configurations and feature flags'))