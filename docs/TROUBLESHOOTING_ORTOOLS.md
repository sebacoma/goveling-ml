# OR-Tools Troubleshooting Guide - Week 4

## 🚨 Quick Diagnosis

### System Health Check
```bash
# Check OR-Tools service status
curl http://localhost:8000/api/v4/monitoring/health

# Check active alerts  
curl http://localhost:8000/api/v4/monitoring/alerts

# Get performance dashboard
curl http://localhost:8000/api/v4/monitoring/dashboard
```

### Emergency Response Flowchart
```
Is OR-Tools responding? 
├─ NO → Check service status, restart if needed
└─ YES → Is success rate >95%?
    ├─ NO → Check alerts, investigate failures
    └─ YES → Is avg response time <5s?
        ├─ NO → Check cache, optimize distance calculations
        └─ YES → System healthy ✅
```

## 🔍 Common Issues & Solutions

### 1. OR-Tools Optimization Failures

#### Issue: "No feasible solution found"
**Symptoms**:
- Error code: `ORTOOLS_INFEASIBLE`
- 0% success rate for specific request patterns
- Logs showing constraint solver failures

**Root Causes**:
```python
# Over-constrained time windows
time_windows = {
    "restaurant": (11, 14),  # Too narrow window
    "museum": (10, 11),      # Conflicts with restaurant
    "park": (14, 15)         # No time for travel
}

# Impossible vehicle routing
vehicle_constraints = {
    "max_walking_distance": 0.1,  # Too restrictive
    "max_daily_distance": 5.0,    # Incompatible with place distribution
    "transport_mode": "walk"       # Doesn't match distance requirements
}
```

**Solutions**:
1. **Relax Time Constraints**:
   ```python
   # Expand time windows
   relaxed_windows = {
       "restaurant": (11, 22),  # Full dining hours
       "museum": (9, 18),       # Museum operating hours  
       "park": (6, 20)          # Daylight hours
   }
   ```

2. **Adjust Vehicle Routing**:
   ```python
   # More realistic constraints
   vehicle_constraints = {
       "max_walking_distance": 2.0,   # Reasonable walking limit
       "max_daily_distance": 50.0,    # Allow for longer distances
       "transport_mode": "mixed"       # Enable multiple transport modes
   }
   ```

3. **Constraint Relaxation Strategy**:
   ```python
   async def solve_with_relaxation(request):
       # Try with full constraints
       try:
           return await ortools_service.optimize(request)
       except ORToolsInfeasibleException:
           # Relax time windows by 1 hour
           request = relax_time_windows(request, hours=1)
           try:
               return await ortools_service.optimize(request)
           except ORToolsInfeasibleException:
               # Further relaxation: remove vehicle constraints
               request = remove_vehicle_constraints(request)
               return await ortools_service.optimize(request)
   ```

#### Issue: "Optimization timeout exceeded"
**Symptoms**:
- Error code: `ORTOOLS_TIMEOUT`
- Requests taking >30 seconds
- Worker processes hanging

**Root Causes**:
- Too many places (>20)
- Complex constraint combinations
- Distance matrix calculation delays
- Insufficient computational resources

**Solutions**:
1. **Immediate Actions**:
   ```bash
   # Increase timeout for complex cases
   export ORTOOLS_TIMEOUT_SECONDS=60
   
   # Scale worker pool
   export ORTOOLS_WORKER_POOL_SIZE=8
   ```

2. **Request Optimization**:
   ```python
   # Pre-filter places by importance
   def filter_critical_places(places, max_count=15):
       scored = [(p, calculate_importance_score(p)) for p in places]
       scored.sort(key=lambda x: x[1], reverse=True)
       return [p for p, score in scored[:max_count]]
   
   # Use hierarchical optimization
   async def hierarchical_optimize(places):
       if len(places) <= 15:
           return await ortools_service.optimize(places)
       
       # Cluster places geographically  
       clusters = cluster_places_by_distance(places, max_cluster_size=10)
       optimized_clusters = []
       
       for cluster in clusters:
           optimized = await ortools_service.optimize(cluster)
           optimized_clusters.append(optimized)
       
       # Optimize cluster connections
       return await optimize_cluster_connections(optimized_clusters)
   ```

3. **Performance Monitoring**:
   ```python
   # Set up timeout monitoring
   @timeout_monitor(threshold_ms=25000)
   async def monitored_optimization(request):
       result = await ortools_service.optimize(request)
       return result
   ```

### 2. Distance Matrix Issues

#### Issue: High API costs and slow responses
**Symptoms**:
- Cache hit rate <50%
- High latency (>5s) for distance calculations
- Excessive API calls to Google Maps/OSRM

**Root Causes**:
```python
# Cache configuration issues
CACHE_CONFIG = {
    "ttl_hours": 1,        # Too short TTL
    "max_entries": 100,    # Too small cache size
    "enable_osrm": False   # Not using OSRM fallback
}

# Inefficient distance requests
distance_requests = [
    (place_a, place_b) for place_a in places for place_b in places
]  # O(n²) without deduplication
```

**Solutions**:
1. **Optimize Cache Configuration**:
   ```python
   # Improved cache settings
   CACHE_CONFIG = {
       "ttl_hours": 24,         # Longer TTL for stable routes
       "max_entries": 10000,    # Larger cache capacity
       "enable_osrm": True,     # Use OSRM for fallback
       "pre_warm": True,        # Pre-calculate common routes
       "compression": True      # Compress cache entries
   }
   ```

2. **Smart Distance Calculation**:
   ```python
   from services.ortools_distance_cache import ORToolsDistanceCache
   
   cache = ORToolsDistanceCache()
   
   # Batch distance requests efficiently
   async def get_optimized_distance_matrix(places):
       # Check cache first
       cached_matrix = await cache.get_cached_matrix(places)
       if cached_matrix:
           return cached_matrix
       
       # Calculate missing distances only
       missing_pairs = cache.get_missing_pairs(places)
       
       # Use parallel calculation for missing pairs
       distances = await cache.calculate_parallel_distances(
           missing_pairs, 
           max_concurrent=10
       )
       
       # Update cache and return complete matrix
       return await cache.build_complete_matrix(places, distances)
   ```

3. **OSRM Integration**:
   ```python
   # Enable OSRM for Chilean cities
   OSRM_CONFIG = {
       "enabled": True,
       "server_url": "http://osrm-server:5000",
       "fallback_to_haversine": True,
       "timeout_seconds": 5
   }
   
   async def get_distance_with_fallback(origin, destination):
       try:
           # Try OSRM first (faster, free)
           return await osrm_service.get_distance(origin, destination)
       except OSRMException:
           # Fallback to Google Maps API
           return await google_maps.get_distance(origin, destination)
   ```

#### Issue: OSRM service unavailable
**Symptoms**:
- Error code: `ORTOOLS_DISTANCE_ERROR`
- Fallback to expensive Google Maps API
- Distance calculation failures

**Root Causes**:
- OSRM server down or unreachable
- Network connectivity issues
- OSRM data corruption

**Solutions**:
1. **Service Health Monitoring**:
   ```python
   async def check_osrm_health():
       try:
           response = await osrm_client.route(
               coordinates=[[-70.6504, -33.4378], [-70.6344, -33.4255]]
           )
           return response.status_code == 200
       except Exception:
           return False
   
   # Automated failover
   if not await check_osrm_health():
       logging.warning("OSRM unavailable, switching to Google Maps API")
       distance_service = GoogleMapsDistanceService()
   ```

2. **OSRM Server Recovery**:
   ```bash
   # Check OSRM server status
   curl http://osrm-server:5000/route/v1/driving/-70.6504,-33.4378;-70.6344,-33.4255
   
   # Restart OSRM service
   docker restart osrm-server
   
   # Verify data files
   ls -la /opt/osrm/data/chile-latest.osrm.*
   ```

3. **Graceful Degradation**:
   ```python
   class RobustDistanceService:
       def __init__(self):
           self.services = [
               OSRMService(priority=1, cost=0),
               GoogleMapsService(priority=2, cost=0.005),
               HaversineService(priority=3, cost=0, accuracy=0.7)
           ]
       
       async def get_distance(self, origin, destination):
           for service in self.services:
               try:
                   result = await service.calculate(origin, destination)
                   await self.record_success(service)
                   return result
               except Exception as e:
                   await self.record_failure(service, e)
                   continue
           
           raise DistanceCalculationError("All distance services failed")
   ```

### 3. Parallel Processing Issues

#### Issue: Worker process crashes
**Symptoms**:
- Error code: `ORTOOLS_WORKER_ERROR`
- Optimization requests hanging
- Memory usage spikes

**Root Causes**:
```python
# Memory leaks in worker processes
def memory_intensive_optimization(places):
    # Large data structures not cleaned up
    distance_matrix = np.zeros((1000, 1000))  # Never freed
    constraint_data = {i: generate_large_data() for i in range(1000)}
    return optimize(places)  # Function exits without cleanup

# Too many concurrent workers
WORKER_CONFIG = {
    "pool_size": 20,        # Too many for available CPU/memory
    "max_queue_size": 100,  # Queue overflow
    "memory_limit": None    # No memory limits
}
```

**Solutions**:
1. **Memory Management**:
   ```python
   import gc
   import psutil
   
   def memory_safe_optimization(places):
       try:
           # Monitor memory usage
           process = psutil.Process()
           initial_memory = process.memory_info().rss
           
           result = optimize_with_constraints(places)
           
           # Explicit cleanup
           del large_data_structures
           gc.collect()
           
           final_memory = process.memory_info().rss
           logging.info(f"Memory used: {(final_memory - initial_memory) / 1024**2:.1f}MB")
           
           return result
       except MemoryError:
           # Emergency cleanup
           gc.collect()
           raise ORToolsMemoryError("Insufficient memory for optimization")
   ```

2. **Worker Pool Configuration**:
   ```python
   # Optimized worker configuration
   import multiprocessing
   
   cpu_count = multiprocessing.cpu_count()
   WORKER_CONFIG = {
       "pool_size": min(cpu_count, 4),      # Don't exceed CPU count
       "max_queue_size": 20,                # Reasonable queue size
       "memory_limit_mb": 512,              # Limit per worker
       "timeout_seconds": 60,               # Worker timeout
       "health_check_interval": 30          # Regular health checks
   }
   ```

3. **Worker Health Monitoring**:
   ```python
   class ORToolsWorkerMonitor:
       def __init__(self):
           self.worker_stats = {}
           self.restart_threshold = 5  # failures before restart
       
       async def monitor_workers(self):
           for worker_id in self.active_workers:
               try:
                   health = await self.check_worker_health(worker_id)
                   if not health.is_healthy:
                       await self.restart_worker(worker_id)
               except Exception as e:
                   logging.error(f"Worker {worker_id} monitor failed: {e}")
                   await self.replace_worker(worker_id)
       
       async def restart_worker(self, worker_id):
           logging.warning(f"Restarting unhealthy worker {worker_id}")
           await self.terminate_worker(worker_id)
           await self.spawn_new_worker()
   ```

### 4. Constraint Solver Performance

#### Issue: Slow constraint satisfaction
**Symptoms**:
- Response times >10 seconds
- High CPU usage during optimization
- Complex constraint combinations timing out

**Root Causes**:
```python
# Inefficient constraint formulation
def create_inefficient_constraints(model, places):
    # O(n³) constraint creation
    for i in places:
        for j in places:
            for k in places:
                model.Add(complex_constraint(i, j, k))  # Exponential complexity

# Over-specification
constraints = {
    "exact_timing": True,       # Forces precise scheduling
    "strict_ordering": True,    # Rigid visit order
    "perfect_optimization": True # Demands global optimum
}
```

**Solutions**:
1. **Efficient Constraint Formulation**:
   ```python
   def create_optimized_constraints(model, places):
       # Use CP-SAT solver with efficient constraints
       from ortools.sat.python import cp_model
       
       # Boolean variables for place assignments
       place_vars = {}
       for day in range(num_days):
           for place in places:
               place_vars[(day, place.id)] = model.NewBoolVar(f'place_{day}_{place.id}')
       
       # Each place visited exactly once
       for place in places:
           model.Add(sum(place_vars[(day, place.id)] for day in range(num_days)) == 1)
       
       # Time window constraints (linear)
       for day in range(num_days):
           day_places = [place_vars[(day, p.id)] for p in places]
           total_time = sum(p.duration * place_vars[(day, p.id)] for p in places)
           model.Add(total_time <= daily_time_limit)
   ```

2. **Heuristic Optimization**:
   ```python
   # Use guided local search for large problems
   def solve_with_heuristics(model, places):
       solver = cp_model.CpSolver()
       
       if len(places) > 15:
           # Enable heuristics for complex cases
           solver.parameters.use_random_lns = True
           solver.parameters.random_seed = 42
           solver.parameters.max_time_in_seconds = 30
           
           # Use construction heuristic
           initial_solution = create_greedy_solution(places)
           solver.parameters.cp_model_presolve = False
       
       status = solver.Solve(model)
       return status, solver
   ```

3. **Progressive Optimization**:
   ```python
   async def progressive_optimization(places):
       # Start with simple optimization
       simple_result = await optimize_with_basic_constraints(places)
       
       if simple_result.quality_score > 0.8:
           return simple_result  # Good enough
       
       # Add more constraints progressively
       enhanced_result = await optimize_with_time_windows(places)
       
       if enhanced_result.quality_score > 0.9:
           return enhanced_result
       
       # Full optimization only if needed
       return await optimize_with_all_constraints(places)
   ```

### 5. Integration Issues

#### Issue: Legacy system fallback failures
**Symptoms**:
- Both OR-Tools and legacy system failing
- No optimization result returned
- Complete service unavailability

**Root Causes**:
```python
# No graceful degradation
async def broken_fallback(request):
    try:
        return await ortools_service.optimize(request)
    except Exception:
        return await legacy_service.optimize(request)  # Legacy also broken
    # No final fallback!

# Circular dependencies
from utils.hybrid_optimizer_v31 import optimize_hybrid
from services.ortools_service import ORToolsService

class ORToolsService:
    async def optimize(self, request):
        if self.should_fallback():
            return await optimize_hybrid(request)  # Circular!
```

**Solutions**:
1. **Robust Fallback Chain**:
   ```python
   async def robust_optimization_chain(request):
       strategies = [
           ("ortools_full", ortools_service.optimize_full),
           ("ortools_simplified", ortools_service.optimize_simple),
           ("city2graph", city2graph_service.optimize),
           ("legacy_hybrid", legacy_service.optimize),
           ("basic_clustering", basic_clustering_service.optimize),
           ("emergency_simple", emergency_simple_optimization)
       ]
       
       for strategy_name, strategy_func in strategies:
           try:
               logging.info(f"Attempting {strategy_name} optimization")
               result = await strategy_func(request)
               
               if validate_result(result):
                   logging.info(f"Success with {strategy_name}")
                   await record_strategy_success(strategy_name)
                   return result
                   
           except Exception as e:
               logging.warning(f"{strategy_name} failed: {e}")
               await record_strategy_failure(strategy_name, e)
               continue
       
       # Emergency fallback - always works
       return create_basic_itinerary(request)
   ```

2. **Break Circular Dependencies**:
   ```python
   # Create abstraction layer
   class OptimizationRouter:
       def __init__(self):
           self.strategies = {}
           self.fallback_chain = []
       
       def register_strategy(self, name, service, priority):
           self.strategies[name] = {
               'service': service,
               'priority': priority,
               'health': True
           }
           self._update_fallback_chain()
       
       async def optimize(self, request):
           for strategy in self.fallback_chain:
               if not strategy['health']:
                   continue
               
               try:
                   return await strategy['service'].optimize(request)
               except Exception:
                   strategy['health'] = False
                   continue
   ```

3. **Health Check Integration**:
   ```python
   async def check_optimization_services():
       services = {
           'ortools': ortools_service,
           'city2graph': city2graph_service,
           'legacy': legacy_service
       }
       
       health_status = {}
       for name, service in services.items():
           try:
               # Simple test optimization
               test_result = await service.test_optimization()
               health_status[name] = {
                   'healthy': True,
                   'response_time': test_result.duration,
                   'last_check': datetime.now()
               }
           except Exception as e:
               health_status[name] = {
                   'healthy': False,
                   'error': str(e),
                   'last_check': datetime.now()
               }
       
       return health_status
   ```

## 🔧 Diagnostic Tools

### 1. Performance Profiler
```python
import cProfile
import pstats

def profile_optimization(request):
    """Profile OR-Tools optimization performance"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = await ortools_service.optimize(request)
    
    profiler.disable() 
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    
    # Save detailed profile
    stats.dump_stats(f'/tmp/ortools_profile_{time.time()}.prof')
    
    # Print top bottlenecks
    stats.print_stats(20)
    
    return result
```

### 2. Memory Monitor
```python
import tracemalloc
import psutil

class MemoryMonitor:
    def __init__(self):
        tracemalloc.start()
        self.baseline = tracemalloc.take_snapshot()
    
    def check_memory_usage(self):
        current = tracemalloc.take_snapshot()
        top_stats = current.compare_to(self.baseline, 'lineno')
        
        print("Top 10 memory consumers:")
        for stat in top_stats[:10]:
            print(f"{stat.traceback.format()}")
            print(f"  Current: {stat.size / 1024**2:.1f}MB")
            print(f"  Growth: +{stat.size_diff / 1024**2:.1f}MB")
    
    def get_system_memory(self):
        process = psutil.Process()
        return {
            'rss': process.memory_info().rss / 1024**2,  # MB
            'vms': process.memory_info().vms / 1024**2,  # MB
            'percent': process.memory_percent()
        }
```

### 3. Request Analyzer
```python
class RequestAnalyzer:
    def analyze_complexity(self, request):
        """Analyze request complexity and predict issues"""
        places = request.get('places', [])
        days = (request['end_date'] - request['start_date']).days + 1
        
        complexity_score = 0
        issues = []
        
        # Place count analysis
        if len(places) > 20:
            complexity_score += 3
            issues.append("High place count may cause timeout")
        elif len(places) > 10:
            complexity_score += 1
            
        # Geographic spread analysis
        coordinates = [(p['lat'], p['lon']) for p in places]
        max_distance = self.calculate_max_distance(coordinates)
        
        if max_distance > 50:  # km
            complexity_score += 2
            issues.append("Wide geographic spread may require vehicle routing")
            
        # Time constraints analysis
        time_windows = self.extract_time_windows(request)
        if time_windows and self.are_time_windows_tight(time_windows):
            complexity_score += 2
            issues.append("Tight time windows may cause infeasible solutions")
        
        return {
            'complexity_score': complexity_score,
            'risk_level': 'HIGH' if complexity_score >= 5 else 'MEDIUM' if complexity_score >= 3 else 'LOW',
            'predicted_issues': issues,
            'recommended_timeout': min(60, 10 + complexity_score * 5)
        }
```

## 📊 Monitoring & Alerting Setup

### 1. Alert Thresholds
```python
ALERT_THRESHOLDS = {
    'success_rate': {
        'warning': 0.95,    # Alert if <95% success
        'critical': 0.90    # Critical if <90% success
    },
    'response_time': {
        'warning': 5000,    # Alert if >5s avg
        'critical': 10000   # Critical if >10s avg
    },
    'error_rate': {
        'warning': 0.05,    # Alert if >5% errors
        'critical': 0.10    # Critical if >10% errors
    },
    'cache_hit_rate': {
        'warning': 0.70,    # Alert if <70% cache hits
        'critical': 0.50    # Critical if <50% cache hits
    }
}
```

### 2. Health Check Endpoint
```python
@app.get("/api/v4/ortools/health-detailed")
async def detailed_health_check():
    """Comprehensive health check for troubleshooting"""
    
    checks = {}
    
    # OR-Tools service check
    try:
        test_result = await ortools_service.test_optimization()
        checks['ortools'] = {
            'status': 'healthy',
            'response_time_ms': test_result.duration,
            'last_success': test_result.timestamp
        }
    except Exception as e:
        checks['ortools'] = {
            'status': 'unhealthy',
            'error': str(e),
            'last_check': datetime.now()
        }
    
    # Distance service check
    try:
        distance = await distance_service.get_test_distance()
        checks['distance_service'] = {
            'status': 'healthy',
            'osrm_available': distance_service.osrm_healthy,
            'cache_hit_rate': distance_service.get_cache_stats()['hit_rate']
        }
    except Exception as e:
        checks['distance_service'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # Worker pool check
    checks['worker_pool'] = {
        'active_workers': parallel_optimizer.get_worker_count(),
        'queue_size': parallel_optimizer.get_queue_size(),
        'worker_health': parallel_optimizer.check_all_workers()
    }
    
    # Overall status
    healthy_services = sum(1 for check in checks.values() if check.get('status') == 'healthy')
    overall_status = 'healthy' if healthy_services == len(checks) else 'degraded' if healthy_services > 0 else 'critical'
    
    return {
        'overall_status': overall_status,
        'timestamp': datetime.now(),
        'checks': checks,
        'recommendations': generate_health_recommendations(checks)
    }
```

### 3. Automated Recovery
```python
class AutoRecoveryService:
    def __init__(self):
        self.recovery_actions = {
            'ortools_timeout': self.restart_ortools_service,
            'cache_miss_high': self.rebuild_distance_cache,
            'worker_unhealthy': self.restart_worker_pool,
            'memory_high': self.trigger_garbage_collection
        }
    
    async def handle_alert(self, alert_type, alert_data):
        """Automatically attempt recovery for known issues"""
        
        if alert_type in self.recovery_actions:
            logging.info(f"Attempting auto-recovery for {alert_type}")
            
            try:
                await self.recovery_actions[alert_type](alert_data)
                logging.info(f"Auto-recovery successful for {alert_type}")
                
                # Verify recovery
                await asyncio.sleep(30)  # Wait for system to stabilize
                if await self.verify_recovery(alert_type):
                    await self.send_recovery_notification(alert_type)
                else:
                    await self.escalate_alert(alert_type, "Auto-recovery failed")
                    
            except Exception as e:
                logging.error(f"Auto-recovery failed for {alert_type}: {e}")
                await self.escalate_alert(alert_type, f"Recovery error: {e}")
    
    async def restart_ortools_service(self, alert_data):
        """Restart OR-Tools service components"""
        await ortools_service.graceful_restart()
        await distance_cache.clear_invalid_entries()
        await parallel_optimizer.restart_workers()
    
    async def rebuild_distance_cache(self, alert_data):
        """Rebuild distance cache for frequently accessed routes"""
        popular_routes = await analytics.get_popular_routes(hours=24)
        await distance_cache.pre_warm_cache(popular_routes)
```

## 📞 Emergency Procedures

### Incident Response Checklist

#### 🚨 Severity 1: Service Down (0% Success Rate)
1. **Immediate Actions (0-5 minutes)**:
   - [ ] Check service health: `curl /api/v4/monitoring/health`
   - [ ] Verify infrastructure: Docker containers, database connections
   - [ ] Enable emergency fallback: `export EMERGENCY_FALLBACK=true`
   - [ ] Notify on-call team via Slack/PagerDuty

2. **Investigation (5-15 minutes)**:
   - [ ] Check recent deployments
   - [ ] Review error logs: `tail -f /var/log/ortools/*.log`
   - [ ] Monitor system resources: CPU, memory, disk
   - [ ] Test individual components

3. **Resolution (15-30 minutes)**:
   - [ ] Restart affected services
   - [ ] Rollback recent changes if necessary
   - [ ] Validate service recovery
   - [ ] Update incident status

#### ⚠️ Severity 2: Performance Degradation (>10s Response Time)
1. **Immediate Actions (0-10 minutes)**:
   - [ ] Check current load and active optimizations
   - [ ] Scale worker pool: `export ORTOOLS_WORKER_POOL_SIZE=8`
   - [ ] Enable performance mode: `export ORTOOLS_PERFORMANCE_MODE=true`

2. **Investigation (10-30 minutes)**:
   - [ ] Analyze slow queries via monitoring dashboard
   - [ ] Check distance cache hit rates
   - [ ] Review constraint complexity
   - [ ] Monitor resource utilization

3. **Resolution (30-60 minutes)**:
   - [ ] Optimize problematic requests
   - [ ] Adjust timeout thresholds
   - [ ] Pre-warm caches for popular routes
   - [ ] Scale infrastructure if needed

#### 🔍 Severity 3: Monitoring Alerts (Success Rate <95%)
1. **Investigation (0-30 minutes)**:
   - [ ] Review alert details and trends
   - [ ] Identify affected request patterns
   - [ ] Check for recent configuration changes

2. **Resolution (30-120 minutes)**:
   - [ ] Adjust algorithm parameters
   - [ ] Update constraint configurations
   - [ ] Enhance fallback strategies
   - [ ] Document lessons learned

### Contact Information
- **Emergency Hotline**: +1-555-ORTOOLS
- **Slack Channel**: #ortools-incidents
- **PagerDuty**: ortools-production-alerts
- **Escalation Manager**: Lead Engineering Manager

---

**Document Version**: 1.0 (Week 4)  
**Last Updated**: January 2025  
**Emergency Review**: Every incident  
**Regular Review**: Monthly