"""Stdio MCP proxy with auto-reload on git commits.

Architecture:
- This process is what Claude Code talks to via stdio (stable, long-lived)
- It spawns the real MCP server as a child process (also stdio)
- All JSON-RPC messages are forwarded transparently in both directions
- Watches .git/refs/heads/ for new commits
- On commit: waits for idle (no in-flight requests), restarts child, replays MCP init

The proxy itself is tiny and never needs restarting. Code changes take effect
on the next commit without restarting Claude Code.

Usage:
    uv run claude-crowed dev

Register with Claude Code:
    claude mcp add --scope user --transport stdio claude-crowed \\
        -- uv run --directory /path/to/claude-crowed claude-crowed dev
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path


class McpReloadProxy:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.server_cmd = [
            sys.executable, "-c",
            "from claude_crowed.server import cli_serve; cli_serve()",
        ]

        self.child: subprocess.Popen | None = None
        self._child_lock = threading.Lock()
        self._child_ready = threading.Event()

        self._init_request: bytes | None = None
        self._init_notification: bytes | None = None

        self._pending_ids: set = set()
        self._pending_lock = threading.Lock()

        self._reload_needed = threading.Event()
        self._stopping = False

    def _start_child(self) -> subprocess.Popen:
        return subprocess.Popen(
            self.server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            cwd=str(self.project_dir),
        )

    def _restart_child(self):
        with self._child_lock:
            self._child_ready.clear()

            if self.child:
                self.child.terminate()
                try:
                    self.child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.child.kill()
                    self.child.wait()

            self.child = self._start_child()

        # Replay MCP init handshake so the new child is in the right state
        if self._init_request and self.child.stdin:
            self.child.stdin.write(self._init_request)
            self.child.stdin.flush()
            # Discard the child's init response (client already has it)
            if self.child.stdout:
                self.child.stdout.readline()
        if self._init_notification and self.child.stdin:
            self.child.stdin.write(self._init_notification)
            self.child.stdin.flush()

        self._child_ready.set()
        self._reload_needed.clear()
        print("[crowed-proxy] Server reloaded", file=sys.stderr, flush=True)

    def _forward_to_child(self, data: bytes):
        self._child_ready.wait()
        with self._child_lock:
            if self.child and self.child.stdin:
                self.child.stdin.write(data)
                self.child.stdin.flush()

    def _reader_loop(self):
        """Read from child stdout, forward to Claude Code stdout."""
        while not self._stopping:
            self._child_ready.wait()
            with self._child_lock:
                child = self.child

            if not child or not child.stdout:
                time.sleep(0.05)
                continue

            try:
                line = child.stdout.readline()
            except (OSError, ValueError):
                time.sleep(0.05)
                continue

            if not line:
                time.sleep(0.05)
                continue

            # Track responses to know when we're idle
            try:
                msg = json.loads(line)
                if "id" in msg and "method" not in msg:  # It's a response
                    with self._pending_lock:
                        self._pending_ids.discard(msg["id"])
                        if self._reload_needed.is_set() and not self._pending_ids:
                            # Forward this last response, then restart
                            sys.stdout.buffer.write(line)
                            sys.stdout.buffer.flush()
                            self._restart_child()
                            continue
            except (json.JSONDecodeError, KeyError):
                pass

            sys.stdout.buffer.write(line)
            sys.stdout.buffer.flush()

    def _watcher_loop(self):
        """Watch .git/refs/heads/ for new commits."""
        refs_dir = self.project_dir / ".git" / "refs" / "heads"
        if not refs_dir.exists():
            print("[crowed-proxy] .git/refs/heads not found, watcher disabled",
                  file=sys.stderr, flush=True)
            return

        def snapshot():
            try:
                return {f.name: f.stat().st_mtime
                        for f in refs_dir.iterdir() if f.is_file()}
            except OSError:
                return {}

        prev = snapshot()
        while not self._stopping:
            time.sleep(1)
            curr = snapshot()
            if curr != prev:
                prev = curr
                print("[crowed-proxy] Commit detected, scheduling reload...",
                      file=sys.stderr, flush=True)
                with self._pending_lock:
                    if not self._pending_ids:
                        self._restart_child()
                    else:
                        self._reload_needed.set()

    def run(self):
        self.child = self._start_child()
        self._child_ready.set()
        print("[crowed-proxy] Started (watching for commits)",
              file=sys.stderr, flush=True)

        reader = threading.Thread(target=self._reader_loop, daemon=True)
        watcher = threading.Thread(target=self._watcher_loop, daemon=True)
        reader.start()
        watcher.start()

        # Main thread: stdin → child
        try:
            for line in sys.stdin.buffer:
                if not line.strip():
                    continue

                try:
                    msg = json.loads(line)
                    method = msg.get("method", "")

                    if method == "initialize":
                        self._init_request = line
                    elif method == "notifications/initialized":
                        self._init_notification = line

                    if "id" in msg and "method" in msg:  # It's a request
                        with self._pending_lock:
                            self._pending_ids.add(msg["id"])
                except json.JSONDecodeError:
                    pass

                self._forward_to_child(line)
        except (KeyboardInterrupt, BrokenPipeError):
            pass
        finally:
            self._stopping = True
            with self._child_lock:
                if self.child:
                    self.child.terminate()


def run_dev():
    project_dir = Path(__file__).resolve().parent.parent.parent
    proxy = McpReloadProxy(project_dir)
    proxy.run()
