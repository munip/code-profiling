with open("server/rl_components.py", "r") as f:
    content = f.read()

old_init = """    def __init__(self, repo_path: Path = None):
        import logging; self._logger = logging.getLogger(__name__); self.repo_path = repo_path or Path("/app"); self._logger.info(f"[GIT] Initialized with repo_path={self.repo_path}")"""

new_init = '''    def __init__(self, repo_path: Path = None):
        import logging
        self._logger = logging.getLogger(__name__)
        self.repo_path = repo_path or Path("/app")
        self._ensure_git_repo()
        self._logger.info(f"[GIT] Initialized with repo_path={self.repo_path}")
    
    def _ensure_git_repo(self):
        """Ensure the directory is a git repository."""
        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            self._logger.info("[GIT] No .git directory found, initializing...")
            try:
                subprocess.run(["git", "init"], cwd=self.repo_path, check=True, capture_output=True)
                subprocess.run(["git", "config", "user.email", "profiler@hfspaces.app"], cwd=self.repo_path, check=True, capture_output=True)
                subprocess.run(["git", "config", "user.name", "Code Profiler"], cwd=self.repo_path, check=True, capture_output=True)
                subprocess.run(["git", "add", "-A"], cwd=self.repo_path, check=True, capture_output=True)
                subprocess.run(["git", "commit", "-m", "baseline: initial code"], cwd=self.repo_path, check=True, capture_output=True)
                self._logger.info("[GIT] Git repo initialized with baseline commit")
            except Exception as e:
                self._logger.error(f"[GIT] Failed to init git repo: {e}")'''

if old_init in content:
    content = content.replace(old_init, new_init)
    with open("server/rl_components.py", "w") as f:
        f.write(content)
    print("SUCCESS: Replaced GitManager.__init__")
else:
    print("Pattern not found in content")
    if "def __init__(self, repo_path" in content:
        print("Found __init__ but pattern didn't match")
