"""Migration utilities for browser-use"""

from .custom_actions import (
	CustomActionMigrator,
	create_legacy_wrapper,
	migrate_custom_action,
	auto_migrate_module
)

from .fork_enhancements import (
	ForkEnhancementsMigrator,
	apply_fork_enhancements,
	create_enhanced_agent
)

__all__ = [
	'CustomActionMigrator',
	'create_legacy_wrapper',
	'migrate_custom_action',
	'auto_migrate_module',
	'ForkEnhancementsMigrator',
	'apply_fork_enhancements',
	'create_enhanced_agent'
]