"""Performance testing and tuning for browser automation"""

import asyncio
import time
import psutil
import gc
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import statistics
import json

from browser_use.utils import time_execution_async


@dataclass
class PerformanceMetric:
	"""Single performance measurement"""
	name: str
	value: float
	unit: str
	timestamp: datetime = field(default_factory=datetime.now)
	metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceReport:
	"""Complete performance analysis report"""
	metrics: List[PerformanceMetric]
	summary: Dict[str, Any]
	recommendations: List[str]
	timestamp: datetime = field(default_factory=datetime.now)
	
	def to_json(self) -> str:
		"""Convert report to JSON"""
		data = {
			"timestamp": self.timestamp.isoformat(),
			"summary": self.summary,
			"recommendations": self.recommendations,
			"metrics": [
				{
					"name": m.name,
					"value": m.value,
					"unit": m.unit,
					"timestamp": m.timestamp.isoformat(),
					"metadata": m.metadata
				}
				for m in self.metrics
			]
		}
		return json.dumps(data, indent=2)


class PerformanceMonitor:
	"""Monitors performance metrics during execution"""
	
	def __init__(self):
		self.metrics: List[PerformanceMetric] = []
		self._start_time = None
		self._start_memory = None
		self._start_cpu = None
		
	async def __aenter__(self):
		"""Start monitoring"""
		self._start_time = time.time()
		self._start_memory = self._get_memory_usage()
		self._start_cpu = psutil.cpu_percent(interval=0.1)
		return self
	
	async def __aexit__(self, exc_type, exc_val, exc_tb):
		"""Stop monitoring and record metrics"""
		duration = time.time() - self._start_time
		end_memory = self._get_memory_usage()
		end_cpu = psutil.cpu_percent(interval=0.1)
		
		self.metrics.extend([
			PerformanceMetric(
				name="execution_time",
				value=duration,
				unit="seconds"
			),
			PerformanceMetric(
				name="memory_used",
				value=end_memory - self._start_memory,
				unit="MB"
			),
			PerformanceMetric(
				name="avg_cpu_usage",
				value=(self._start_cpu + end_cpu) / 2,
				unit="percent"
			)
		])
	
	def _get_memory_usage(self) -> float:
		"""Get current memory usage in MB"""
		process = psutil.Process()
		return process.memory_info().rss / 1024 / 1024
	
	def add_metric(self, name: str, value: float, unit: str, **metadata) -> None:
		"""Add a custom metric"""
		self.metrics.append(PerformanceMetric(
			name=name,
			value=value,
			unit=unit,
			metadata=metadata
		))


class PerformanceTuner:
	"""Automatically tunes performance parameters"""
	
	def __init__(self):
		self.optimization_history: List[Dict[str, Any]] = []
		self.best_config: Optional[Dict[str, Any]] = None
		self.best_score: float = float('inf')
		
		# Tunable parameters
		self.parameters = {
			"cache_ttl": {"min": 60, "max": 600, "step": 60},
			"max_parallel_actions": {"min": 1, "max": 10, "step": 1},
			"dom_scan_interval": {"min": 30, "max": 300, "step": 30},
			"token_compression_ratio": {"min": 0.5, "max": 0.9, "step": 0.1},
			"prefetch_confidence_threshold": {"min": 0.2, "max": 0.8, "step": 0.1}
		}
	
	async def auto_tune(
		self,
		test_function: Callable,
		iterations: int = 10,
		optimization_target: str = "execution_time"
	) -> Dict[str, Any]:
		"""Automatically tune parameters to optimize performance"""
		
		for i in range(iterations):
			# Generate configuration
			if i == 0:
				# Start with defaults
				config = self._get_default_config()
			else:
				# Use optimization strategy
				config = self._generate_next_config()
			
			# Test configuration
			monitor = PerformanceMonitor()
			
			async with monitor:
				await test_function(config)
			
			# Evaluate performance
			score = self._calculate_score(monitor.metrics, optimization_target)
			
			# Record result
			self.optimization_history.append({
				"iteration": i,
				"config": config,
				"score": score,
				"metrics": monitor.metrics
			})
			
			# Update best if improved
			if score < self.best_score:
				self.best_score = score
				self.best_config = config.copy()
		
		return self.best_config
	
	def _get_default_config(self) -> Dict[str, Any]:
		"""Get default configuration"""
		return {
			"cache_ttl": 300,
			"max_parallel_actions": 3,
			"dom_scan_interval": 60,
			"token_compression_ratio": 0.7,
			"prefetch_confidence_threshold": 0.5
		}
	
	def _generate_next_config(self) -> Dict[str, Any]:
		"""Generate next configuration to test"""
		if not self.optimization_history:
			return self._get_default_config()
		
		# Use gradient descent-like approach
		last_config = self.optimization_history[-1]["config"]
		last_score = self.optimization_history[-1]["score"]
		
		# Find parameter that had most impact
		best_param_impact = None
		best_param_name = None
		
		if len(self.optimization_history) >= 2:
			prev_config = self.optimization_history[-2]["config"]
			prev_score = self.optimization_history[-2]["score"]
			
			score_improvement = prev_score - last_score
			
			for param_name in self.parameters:
				if last_config[param_name] != prev_config[param_name]:
					param_change = last_config[param_name] - prev_config[param_name]
					impact = score_improvement / param_change if param_change != 0 else 0
					
					if best_param_impact is None or abs(impact) > abs(best_param_impact):
						best_param_impact = impact
						best_param_name = param_name
		
		# Generate new config
		new_config = last_config.copy()
		
		if best_param_name and best_param_impact > 0:
			# Continue in the same direction
			param_info = self.parameters[best_param_name]
			step = param_info["step"] * (2 if abs(best_param_impact) > 0.1 else 1)
			
			if best_param_impact > 0:
				new_value = last_config[best_param_name] + step
			else:
				new_value = last_config[best_param_name] - step
			
			# Clamp to bounds
			new_value = max(param_info["min"], min(param_info["max"], new_value))
			new_config[best_param_name] = new_value
		else:
			# Random exploration
			import random
			param_name = random.choice(list(self.parameters.keys()))
			param_info = self.parameters[param_name]
			
			new_value = last_config[param_name] + random.choice([-1, 1]) * param_info["step"]
			new_value = max(param_info["min"], min(param_info["max"], new_value))
			new_config[param_name] = new_value
		
		return new_config
	
	def _calculate_score(self, metrics: List[PerformanceMetric], target: str) -> float:
		"""Calculate optimization score"""
		# Find target metric
		target_metric = next((m for m in metrics if m.name == target), None)
		
		if not target_metric:
			return float('inf')
		
		# Lower is better for most metrics
		return target_metric.value
	
	def get_tuning_report(self) -> PerformanceReport:
		"""Generate tuning report"""
		if not self.optimization_history:
			return PerformanceReport(
				metrics=[],
				summary={},
				recommendations=["No tuning data available"]
			)
		
		# Analyze results
		scores = [h["score"] for h in self.optimization_history]
		configs = [h["config"] for h in self.optimization_history]
		
		# Parameter impact analysis
		parameter_impacts = {}
		for param_name in self.parameters:
			values = [c[param_name] for c in configs]
			if len(set(values)) > 1:
				# Calculate correlation with score
				correlation = self._calculate_correlation(values, scores)
				parameter_impacts[param_name] = correlation
		
		# Generate recommendations
		recommendations = []
		
		for param_name, impact in sorted(parameter_impacts.items(), key=lambda x: abs(x[1]), reverse=True):
			if abs(impact) > 0.3:
				if impact > 0:
					recommendations.append(f"Decrease {param_name} for better performance")
				else:
					recommendations.append(f"Increase {param_name} for better performance")
		
		if self.best_config:
			recommendations.append(f"Best configuration found: {json.dumps(self.best_config, indent=2)}")
		
		# Create summary
		summary = {
			"iterations": len(self.optimization_history),
			"best_score": self.best_score,
			"score_improvement": (scores[0] - self.best_score) / scores[0] * 100 if scores else 0,
			"parameter_impacts": parameter_impacts
		}
		
		# Collect all metrics
		all_metrics = []
		for history in self.optimization_history:
			all_metrics.extend(history.get("metrics", []))
		
		return PerformanceReport(
			metrics=all_metrics,
			summary=summary,
			recommendations=recommendations
		)
	
	def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
		"""Calculate Pearson correlation coefficient"""
		if len(x) != len(y) or len(x) < 2:
			return 0.0
		
		x_mean = statistics.mean(x)
		y_mean = statistics.mean(y)
		
		numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
		
		x_variance = sum((xi - x_mean) ** 2 for xi in x)
		y_variance = sum((yi - y_mean) ** 2 for yi in y)
		
		denominator = (x_variance * y_variance) ** 0.5
		
		if denominator == 0:
			return 0.0
		
		return numerator / denominator


class PerformanceBenchmark:
	"""Benchmarks different operations"""
	
	def __init__(self):
		self.results: Dict[str, List[float]] = {}
	
	async def benchmark_operation(
		self,
		name: str,
		operation: Callable,
		iterations: int = 10,
		warmup: int = 2
	) -> Dict[str, float]:
		"""Benchmark a specific operation"""
		times = []
		
		# Warmup runs
		for _ in range(warmup):
			await operation()
		
		# Actual benchmark
		for _ in range(iterations):
			start = time.perf_counter()
			await operation()
			duration = time.perf_counter() - start
			times.append(duration)
		
		# Store results
		self.results[name] = times
		
		# Calculate statistics
		return {
			"mean": statistics.mean(times),
			"median": statistics.median(times),
			"stdev": statistics.stdev(times) if len(times) > 1 else 0,
			"min": min(times),
			"max": max(times),
			"p95": sorted(times)[int(len(times) * 0.95)] if times else 0
		}
	
	async def run_standard_benchmarks(self, agent: Any) -> PerformanceReport:
		"""Run standard set of benchmarks"""
		benchmarks = [
			("intent_analysis", lambda: agent.intent_analyzer.analyze("Click the submit button")),
			("element_resolution", lambda: self._benchmark_element_resolution(agent)),
			("perception_fusion", lambda: self._benchmark_perception(agent)),
			("cache_performance", lambda: self._benchmark_cache(agent)),
			("token_optimization", lambda: self._benchmark_token_optimization(agent))
		]
		
		metrics = []
		
		for name, operation in benchmarks:
			stats = await self.benchmark_operation(name, operation)
			
			metrics.append(PerformanceMetric(
				name=f"{name}_avg",
				value=stats["mean"] * 1000,  # Convert to ms
				unit="ms",
				metadata=stats
			))
		
		# Generate summary
		summary = {
			"total_benchmarks": len(benchmarks),
			"avg_execution_time": statistics.mean([m.value for m in metrics]),
			"fastest_operation": min(metrics, key=lambda m: m.value).name,
			"slowest_operation": max(metrics, key=lambda m: m.value).name
		}
		
		# Recommendations based on results
		recommendations = []
		
		for metric in metrics:
			if metric.value > 100:  # Over 100ms
				recommendations.append(f"Consider optimizing {metric.name} (currently {metric.value:.1f}ms)")
		
		return PerformanceReport(
			metrics=metrics,
			summary=summary,
			recommendations=recommendations
		)
	
	async def _benchmark_element_resolution(self, agent: Any) -> None:
		"""Benchmark element resolution"""
		from browser_use.core.intent.views import ElementIntent
		
		element_intent = ElementIntent(
			description="Submit button",
			element_type="button"
		)
		
		# Mock perception data
		perception_data = {
			"url": "https://example.com",
			"page": None  # Would be actual page in real scenario
		}
		
		# This would fail in real scenario without page, but shows the structure
		try:
			await agent.element_resolver.resolve_element(
				element_intent,
				perception_data,
				None
			)
		except:
			pass
	
	async def _benchmark_perception(self, agent: Any) -> None:
		"""Benchmark perception fusion"""
		# Mock perception results
		from browser_use.perception.base import PerceptionResult, PerceptionElement
		
		mock_results = {
			"dom": PerceptionResult(elements=[
				PerceptionElement(type="button", text="Submit")
				for _ in range(50)
			]),
			"vision": PerceptionResult(elements=[
				PerceptionElement(type="button", text="Submit")
				for _ in range(30)
			])
		}
		
		await agent.perception_fusion.fuse_results(mock_results)
	
	async def _benchmark_cache(self, agent: Any) -> None:
		"""Benchmark cache operations"""
		from browser_use.core.cache import get_intelligent_cache
		
		cache = get_intelligent_cache()
		
		# Write and read operations
		for i in range(100):
			await cache.set(f"key_{i}", f"value_{i}")
		
		for i in range(100):
			await cache.get(f"key_{i}")
	
	async def _benchmark_token_optimization(self, agent: Any) -> None:
		"""Benchmark token optimization"""
		from browser_use.core.optimization import TokenOptimizer
		
		optimizer = TokenOptimizer()
		
		# Generate large text
		large_text = "This is a test. " * 1000
		
		optimizer.optimize_prompt(large_text, max_tokens=1000)


# Performance profiling decorator
def profile_performance(name: Optional[str] = None):
	"""Decorator to profile function performance"""
	def decorator(func: Callable) -> Callable:
		async def wrapper(*args, **kwargs):
			monitor = PerformanceMonitor()
			
			async with monitor:
				result = await func(*args, **kwargs)
			
			# Log metrics
			func_name = name or func.__name__
			for metric in monitor.metrics:
				print(f"{func_name} - {metric.name}: {metric.value:.2f} {metric.unit}")
			
			return result
		
		return wrapper
	
	return decorator