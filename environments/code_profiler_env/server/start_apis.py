"""
API Process Manager for Code Profiler Environment.

Starts and manages Python, Java, and C++ API servers as background processes.
All APIs run on different ports and can be profiled by the OpenEnv server.
"""

import subprocess
import threading
import time
import logging
import os
import signal
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

JAVA_MAIN_CLASS = "com.ecommerce.api.ECommerceAPI"
CPP_BINARY = "/app/cpp_src/build/ecommerce_api"
PYTHON_API_PORT = 5000
JAVA_API_PORT = 5001
CPP_API_PORT = 5002


@dataclass
class APIServer:
    name: str
    port: int
    process: Optional[subprocess.Popen] = None
    running: bool = False


class APIServerManager:
    """Manages Python, Java, and C++ API servers."""

    def __init__(self):
        self.python_server = APIServer(name="python", port=PYTHON_API_PORT)
        self.java_server = APIServer(name="java", port=JAVA_API_PORT)
        self.cpp_server = APIServer(name="cpp", port=CPP_API_PORT)
        self.servers = [self.python_server, self.java_server, self.cpp_server]
        self._startup_timeout = 30

    def start_python_api(self) -> bool:
        """Start Python Flask API server."""
        try:
            if self.python_server.running:
                logger.info("Python API already running")
                return True

            env = os.environ.copy()
            env["FLASK_ENV"] = "production"
            env["PYTHONUNBUFFERED"] = "1"

            self.python_server.process = subprocess.Popen(
                ["python", "/app/python_api.py"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != "nt" else None,
            )

            if self._wait_for_server(self.python_server.port):
                self.python_server.running = True
                logger.info(f"Python API started on port {PYTHON_API_PORT}")
                return True
            else:
                logger.error("Python API failed to start")
                return False
        except Exception as e:
            logger.error(f"Error starting Python API: {e}")
            return False

    def start_java_api(self) -> bool:
        """Start Java API server."""
        try:
            if self.java_server.running:
                logger.info("Java API already running")
                return True

            self.java_server.process = subprocess.Popen(
                ["java", "-cp", "/app/java_classes", JAVA_MAIN_CLASS],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != "nt" else None,
            )

            if self._wait_for_server(self.java_server.port, timeout=10):
                self.java_server.running = True
                logger.info(f"Java API started on port {JAVA_API_PORT}")
                return True
            else:
                logger.warning("Java API may not be running (non-HTTP server)")
                self.java_server.running = True
                return True
        except Exception as e:
            logger.error(f"Error starting Java API: {e}")
            return False

    def start_cpp_api(self) -> bool:
        """Start C++ API server."""
        try:
            if self.cpp_server.running:
                logger.info("C++ API already running")
                return True

            if not os.path.exists(CPP_BINARY):
                logger.error(f"C++ binary not found: {CPP_BINARY}")
                return False

            self.cpp_server.process = subprocess.Popen(
                [CPP_BINARY],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != "nt" else None,
            )

            if self._wait_for_server(self.cpp_server.port, timeout=10):
                self.cpp_server.running = True
                logger.info(f"C++ API started on port {CPP_API_PORT}")
                return True
            else:
                logger.warning("C++ API may not be running (non-HTTP server)")
                self.cpp_server.running = True
                return True
        except Exception as e:
            logger.error(f"Error starting C++ API: {e}")
            return False

    def start_all(self) -> Dict[str, bool]:
        """Start all API servers."""
        results = {
            "python": self.start_python_api(),
            "java": self.start_java_api(),
            "cpp": self.start_cpp_api(),
        }
        return results

    def stop_python_api(self):
        """Stop Python API server."""
        if self.python_server.process:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(self.python_server.process.pid), signal.SIGTERM)
                else:
                    self.python_server.process.terminate()
                self.python_server.process.wait(timeout=5)
            except Exception:
                pass
            self.python_server.running = False
            self.python_server.process = None

    def stop_java_api(self):
        """Stop Java API server."""
        if self.java_server.process:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(self.java_server.process.pid), signal.SIGTERM)
                else:
                    self.java_server.process.terminate()
                self.java_server.process.wait(timeout=5)
            except Exception:
                pass
            self.java_server.running = False
            self.java_server.process = None

    def stop_cpp_api(self):
        """Stop C++ API server."""
        if self.cpp_server.process:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(self.cpp_server.process.pid), signal.SIGTERM)
                else:
                    self.cpp_server.process.terminate()
                self.cpp_server.process.wait(timeout=5)
            except Exception:
                pass
            self.cpp_server.running = False
            self.cpp_server.process = None

    def stop_all(self):
        """Stop all API servers."""
        self.stop_python_api()
        self.stop_java_api()
        self.stop_cpp_api()
        logger.info("All API servers stopped")

    def _wait_for_server(self, port: int, timeout: int = None) -> bool:
        """Wait for a server to become available."""
        import httpx

        if timeout is None:
            timeout = self._startup_timeout

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = httpx.get(f"http://localhost:{port}/health", timeout=2.0)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def get_status(self) -> Dict[str, dict]:
        """Get status of all servers."""
        return {
            "python": {
                "running": self.python_server.running,
                "port": self.python_server.port,
                "pid": self.python_server.process.pid if self.python_server.process else None,
            },
            "java": {
                "running": self.java_server.running,
                "port": self.java_server.port,
                "pid": self.java_server.process.pid if self.java_server.process else None,
            },
            "cpp": {
                "running": self.cpp_server.running,
                "port": self.cpp_server.port,
                "pid": self.cpp_server.process.pid if self.cpp_server.process else None,
            },
        }


# Global instance
api_manager = APIServerManager()


def start_apis_on_boot():
    """Start all APIs when the container boots."""
    logger.info("Starting all API servers...")
    results = api_manager.start_all()
    for name, success in results.items():
        if success:
            logger.info(f"  {name}: OK")
        else:
            logger.warning(f"  {name}: FAILED")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = start_apis_on_boot()
    print(f"\nAPI Server Status:")
    for name, success in results.items():
        print(f"  {name}: {'OK' if success else 'FAILED'}")

    if all(results.values()):
        print("\nAll APIs started successfully. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping APIs...")
            api_manager.stop_all()
    else:
        print("\nSome APIs failed to start. Check logs for details.")
