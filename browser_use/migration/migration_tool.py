"""Comprehensive migration tool for transitioning to next-generation architecture"""

import ast
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json
from dataclasses import dataclass
import click


@dataclass
class MigrationIssue:
	"""Issue found during migration analysis"""
	file_path: str
	line_number: int
	issue_type: str
	description: str
	severity: str  # 'error', 'warning', 'info'
	suggested_fix: Optional[str] = None


@dataclass
class MigrationReport:
	"""Complete migration analysis report"""
	total_files: int
	files_to_migrate: List[str]
	issues: List[MigrationIssue]
	estimated_effort: str
	recommendations: List[str]
	
	def to_json(self) -> str:
		"""Convert report to JSON"""
		return json.dumps({
			"total_files": self.total_files,
			"files_to_migrate": self.files_to_migrate,
			"issue_count": len(self.issues),
			"issues_by_severity": self._count_by_severity(),
			"estimated_effort": self.estimated_effort,
			"recommendations": self.recommendations
		}, indent=2)
	
	def _count_by_severity(self) -> Dict[str, int]:
		"""Count issues by severity"""
		counts = {"error": 0, "warning": 0, "info": 0}
		for issue in self.issues:
			counts[issue.severity] = counts.get(issue.severity, 0) + 1
		return counts


class CodeMigrationAnalyzer:
	"""Analyzes code for migration needs"""
	
	def __init__(self):
		self.legacy_patterns = {
			# Import patterns
			r'from browser_use\.agent\.service import Agent': 'Legacy Agent import',
			r'from browser_use\.controller\.service import Controller': 'Legacy Controller import',
			r'from browser_use\.controller\.actions import': 'Legacy action import',
			
			# Usage patterns
			r'Agent\s*\(': 'Legacy Agent instantiation',
			r'Controller\s*\(': 'Legacy Controller instantiation',
			r'\.act\s*\(': 'Legacy act method',
			r'\.multi_act\s*\(': 'Legacy multi_act method',
			r'ActionModel\s*\(': 'Legacy ActionModel usage',
			r'coordinate\s*=': 'Coordinate-based interaction',
			
			# Custom action patterns
			r'@action\s*\(': 'Legacy action decorator',
			r'register_action\s*\(': 'Legacy action registration',
		}
		
		self.migration_mappings = {
			'Agent': 'NextGenBrowserAgent or BackwardCompatibleAgent',
			'Controller': 'ParallelActionOrchestrator',
			'act()': 'execute_task() or execute_intent_directly()',
			'multi_act()': 'execute_intent_directly() with parallel sub-intents',
			'ActionModel': 'Action',
			'coordinate=': 'Use ElementIntent with visual grounding',
		}
	
	def analyze_file(self, file_path: Path) -> List[MigrationIssue]:
		"""Analyze a single file for migration issues"""
		issues = []
		
		try:
			with open(file_path, 'r') as f:
				content = f.read()
				lines = content.split('\n')
			
			# Check for legacy patterns
			for line_num, line in enumerate(lines, 1):
				for pattern, description in self.legacy_patterns.items():
					if re.search(pattern, line):
						# Determine severity
						severity = 'error' if 'import' in description else 'warning'
						
						# Get suggested fix
						for old, new in self.migration_mappings.items():
							if old in line:
								suggested_fix = f"Replace {old} with {new}"
								break
						else:
							suggested_fix = None
						
						issues.append(MigrationIssue(
							file_path=str(file_path),
							line_number=line_num,
							issue_type=description,
							description=f"Found legacy pattern: {pattern}",
							severity=severity,
							suggested_fix=suggested_fix
						))
			
			# AST analysis for more complex patterns
			try:
				tree = ast.parse(content)
				issues.extend(self._analyze_ast(tree, file_path))
			except SyntaxError:
				pass
			
		except Exception as e:
			issues.append(MigrationIssue(
				file_path=str(file_path),
				line_number=0,
				issue_type="Analysis Error",
				description=f"Failed to analyze file: {str(e)}",
				severity="error"
			))
		
		return issues
	
	def _analyze_ast(self, tree: ast.AST, file_path: Path) -> List[MigrationIssue]:
		"""Analyze AST for complex patterns"""
		issues = []
		
		for node in ast.walk(tree):
			# Check for class inheritance
			if isinstance(node, ast.ClassDef):
				for base in node.bases:
					if isinstance(base, ast.Name) and base.id in ['Agent', 'Controller']:
						issues.append(MigrationIssue(
							file_path=str(file_path),
							line_number=node.lineno,
							issue_type="Legacy class inheritance",
							description=f"Class inherits from legacy {base.id}",
							severity="error",
							suggested_fix=f"Inherit from new base classes or use composition"
						))
			
			# Check for specific method calls
			if isinstance(node, ast.Call):
				if isinstance(node.func, ast.Attribute):
					if node.func.attr in ['act', 'multi_act', 'register_action']:
						issues.append(MigrationIssue(
							file_path=str(file_path),
							line_number=node.lineno,
							issue_type="Legacy method call",
							description=f"Calling legacy method: {node.func.attr}",
							severity="warning",
							suggested_fix=self.migration_mappings.get(f"{node.func.attr}()")
						))
		
		return issues
	
	def analyze_project(self, project_path: Path) -> MigrationReport:
		"""Analyze entire project"""
		all_issues = []
		files_to_migrate = []
		total_files = 0
		
		# Find all Python files
		for py_file in project_path.rglob("*.py"):
			# Skip test files and migration tools
			if "test" in str(py_file) or "migration" in str(py_file):
				continue
			
			total_files += 1
			issues = self.analyze_file(py_file)
			
			if issues:
				all_issues.extend(issues)
				files_to_migrate.append(str(py_file.relative_to(project_path)))
		
		# Estimate effort
		effort = self._estimate_effort(all_issues)
		
		# Generate recommendations
		recommendations = self._generate_recommendations(all_issues)
		
		return MigrationReport(
			total_files=total_files,
			files_to_migrate=files_to_migrate,
			issues=all_issues,
			estimated_effort=effort,
			recommendations=recommendations
		)
	
	def _estimate_effort(self, issues: List[MigrationIssue]) -> str:
		"""Estimate migration effort"""
		error_count = sum(1 for i in issues if i.severity == 'error')
		warning_count = sum(1 for i in issues if i.severity == 'warning')
		
		# Simple estimation formula
		hours = (error_count * 0.5) + (warning_count * 0.25)
		
		if hours < 2:
			return "Low (< 2 hours)"
		elif hours < 8:
			return f"Medium ({hours:.1f} hours)"
		else:
			return f"High ({hours:.1f} hours)"
	
	def _generate_recommendations(self, issues: List[MigrationIssue]) -> List[str]:
		"""Generate migration recommendations"""
		recommendations = []
		
		# Count issue types
		issue_types = {}
		for issue in issues:
			issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1
		
		# Generate specific recommendations
		if issue_types.get('Legacy Agent import', 0) > 0:
			recommendations.append(
				"Replace Agent imports with NextGenBrowserAgent or BackwardCompatibleAgent"
			)
		
		if issue_types.get('Coordinate-based interaction', 0) > 0:
			recommendations.append(
				"Migrate coordinate-based interactions to intent-based with visual grounding"
			)
		
		if issue_types.get('Legacy action decorator', 0) > 0:
			recommendations.append(
				"Use migrate_custom_action decorator for custom actions"
			)
		
		# General recommendations
		recommendations.extend([
			"Run comprehensive tests after migration",
			"Consider using BackwardCompatibleAgent for gradual migration",
			"Review performance improvements with new architecture"
		])
		
		return recommendations


class CodeMigrator:
	"""Automatically migrates code to new architecture"""
	
	def __init__(self):
		self.transformations = {
			# Import transformations
			r'from browser_use\.agent\.service import Agent': 
				'from browser_use.agent.compatibility import BackwardCompatibleAgent as Agent',
			
			r'from browser_use\.controller\.service import Controller':
				'from browser_use.agent.next_gen_agent import NextGenBrowserAgent',
			
			# Simple replacements
			r'ActionModel\(': 'Action(',
			r'\.act\(([^)]+)\)': r'.execute_task(\1)',
		}
	
	def migrate_file(self, file_path: Path, backup: bool = True) -> Tuple[bool, List[str]]:
		"""Migrate a single file"""
		changes = []
		
		try:
			# Read file
			with open(file_path, 'r') as f:
				content = f.read()
				original_content = content
			
			# Apply transformations
			for pattern, replacement in self.transformations.items():
				new_content = re.sub(pattern, replacement, content)
				if new_content != content:
					changes.append(f"Applied transformation: {pattern}")
					content = new_content
			
			# Only write if changes were made
			if content != original_content:
				if backup:
					backup_path = file_path.with_suffix('.py.bak')
					with open(backup_path, 'w') as f:
						f.write(original_content)
				
				with open(file_path, 'w') as f:
					f.write(content)
				
				return True, changes
			
			return False, []
			
		except Exception as e:
			return False, [f"Error: {str(e)}"]
	
	def migrate_project(
		self,
		project_path: Path,
		files_to_migrate: List[str],
		backup: bool = True
	) -> Dict[str, Any]:
		"""Migrate entire project"""
		results = {
			"migrated": [],
			"failed": [],
			"total_changes": 0
		}
		
		for file_path_str in files_to_migrate:
			file_path = project_path / file_path_str
			
			success, changes = self.migrate_file(file_path, backup)
			
			if success:
				results["migrated"].append({
					"file": file_path_str,
					"changes": changes
				})
				results["total_changes"] += len(changes)
			else:
				results["failed"].append({
					"file": file_path_str,
					"error": changes[0] if changes else "Unknown error"
				})
		
		return results


@click.group()
def cli():
	"""Browser-Use Migration Tool"""
	pass


@cli.command()
@click.argument('project_path', type=click.Path(exists=True))
@click.option('--output', '-o', help='Output file for report', default='migration_report.json')
def analyze(project_path, output):
	"""Analyze project for migration needs"""
	click.echo(f"Analyzing project at {project_path}...")
	
	analyzer = CodeMigrationAnalyzer()
	report = analyzer.analyze_project(Path(project_path))
	
	# Display summary
	click.echo(f"\nAnalysis Complete:")
	click.echo(f"Total files scanned: {report.total_files}")
	click.echo(f"Files needing migration: {len(report.files_to_migrate)}")
	
	severity_counts = report._count_by_severity()
	click.echo(f"\nIssues found:")
	for severity, count in severity_counts.items():
		click.echo(f"  {severity}: {count}")
	
	click.echo(f"\nEstimated effort: {report.estimated_effort}")
	
	click.echo(f"\nRecommendations:")
	for rec in report.recommendations:
		click.echo(f"  - {rec}")
	
	# Save detailed report
	with open(output, 'w') as f:
		f.write(report.to_json())
	
	click.echo(f"\nDetailed report saved to: {output}")


@cli.command()
@click.argument('project_path', type=click.Path(exists=True))
@click.option('--report', '-r', help='Migration report file', default='migration_report.json')
@click.option('--no-backup', is_flag=True, help='Skip creating backup files')
@click.option('--dry-run', is_flag=True, help='Show what would be changed without modifying files')
def migrate(project_path, report, no_backup, dry_run):
	"""Migrate project to new architecture"""
	# Load report
	try:
		with open(report, 'r') as f:
			report_data = json.load(f)
		files_to_migrate = report_data['files_to_migrate']
	except Exception as e:
		click.echo(f"Error loading report: {e}")
		click.echo("Please run 'analyze' command first")
		return
	
	if dry_run:
		click.echo("DRY RUN - No files will be modified")
	
	click.echo(f"Migrating {len(files_to_migrate)} files...")
	
	migrator = CodeMigrator()
	
	if dry_run:
		# Just show what would be done
		for file_path in files_to_migrate:
			click.echo(f"Would migrate: {file_path}")
	else:
		results = migrator.migrate_project(
			Path(project_path),
			files_to_migrate,
			backup=not no_backup
		)
		
		click.echo(f"\nMigration Complete:")
		click.echo(f"Successfully migrated: {len(results['migrated'])} files")
		click.echo(f"Failed: {len(results['failed'])} files")
		click.echo(f"Total changes: {results['total_changes']}")
		
		if results['failed']:
			click.echo("\nFailed files:")
			for failure in results['failed']:
				click.echo(f"  {failure['file']}: {failure['error']}")


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
def check_file(file_path):
	"""Check a single file for migration needs"""
	analyzer = CodeMigrationAnalyzer()
	issues = analyzer.analyze_file(Path(file_path))
	
	if not issues:
		click.echo("No migration issues found!")
	else:
		click.echo(f"Found {len(issues)} issues:")
		for issue in issues:
			click.echo(f"\nLine {issue.line_number}: {issue.issue_type}")
			click.echo(f"  {issue.description}")
			if issue.suggested_fix:
				click.echo(f"  Suggested fix: {issue.suggested_fix}")


if __name__ == '__main__':
	cli()