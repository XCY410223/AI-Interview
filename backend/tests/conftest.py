"""pytest 全局配置：确保 backend/ 在 sys.path，便于测试内 `import app`。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
