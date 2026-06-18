import os
import json
from datetime import datetime, timedelta

def generate_logs():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    now = datetime.now()
    
    # 1. backend.log
    backend_log_path = os.path.join(logs_dir, "backend.log")
    with open(backend_log_path, "w", encoding="utf-8") as f:
        f.write(f"[{now - timedelta(minutes=5)}] INFO: Starting FastAPI worker\n")
        f.write(f"[{now - timedelta(minutes=4)}] INFO: Connecting to Database...\n")
        f.write(f"[{now - timedelta(minutes=2)}] ERROR: Timed out waiting for connection from pool. Pool size: 10, Active: 10\n")
        f.write(f"[{now - timedelta(minutes=1)}] ERROR: Exception in analyze_incident\nTraceback (most recent call last):\n  File \"main.py\", line 50, in analyze_incident\n    db.query()\nsqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 10 reached, connection timed out, timeout 30.00\n")
        
    # 2. db.log
    db_log_path = os.path.join(logs_dir, "db.log")
    with open(db_log_path, "w", encoding="utf-8") as f:
        f.write(f"[{now - timedelta(minutes=10)}] [Note] InnoDB: Buffer pool(s) load completed at 230918\n")
        f.write(f"[{now - timedelta(minutes=3)}] [Warning] Aborted connection 1024 to db: 'itsm_db' user: 'admin' host: 'localhost' (Got timeout reading communication packets)\n")
        f.write(f"[{now - timedelta(minutes=1)}] [ERROR] Deadlock found when trying to get lock; try restarting transaction\n")
        
    # 3. frontend.log
    frontend_log_path = os.path.join(logs_dir, "frontend.log")
    with open(frontend_log_path, "w", encoding="utf-8") as f:
        f.write(f"[{now - timedelta(minutes=2)}] INFO: User navigation to /dashboard\n")
        f.write(f"[{now - timedelta(minutes=1)}] ERROR: API Request failed. Status: 500, Message: Internal Server Error\n")
        
    # 4. health_status.json
    health_path = os.path.join(logs_dir, "health_status.json")
    health_data = {
        "timestamp": str(now),
        "backend_server": {
            "status": "Warning",
            "cpu_usage": "78%",
            "memory_usage": "65%",
            "active_connections": 1500
        },
        "database": {
            "status": "Critical",
            "connection_pool_usage": "100%",
            "active_queries": 200,
            "deadlocks_detected": 1
        },
        "frontend": {
            "status": "Healthy",
            "latency": "120ms"
        }
    }
    with open(health_path, "w", encoding="utf-8") as f:
        json.dump(health_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    generate_logs()
