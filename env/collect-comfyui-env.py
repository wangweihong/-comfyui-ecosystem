#!/usr/bin/env python3
"""
ComfyUI Environment Info Collector
采集 ComfyUI 的前后端版本、运行命令行参数、环境变量、GPU 信息、节点版本信息、
节点 Git 远程地址、当前 Python 环境的包列表，以及指定目录下的所有模型文件。
"""

import json
import os
import sys
import subprocess
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Set

try:
    import torch
except ImportError:
    torch = None

try:
    import requests
except ImportError:
    requests = None


class ComfyUIInfoCollector:
    """ComfyUI 环境信息采集器"""

    # 常见模型文件扩展名
    MODEL_EXTENSIONS: Set[str] = {
        '.safetensors', '.ckpt', '.pt', '.pth', '.bin', '.onnx', '.pkl', '.pb'
#        '.diffusion_pytorch_model', '.vae', '.yaml', '.json', '.txt', '.csv'
    }

    def __init__(
        self,
        comfyui_path: Optional[str] = None,
        server_url: str = "http://127.0.0.1:8188",
        models_root: Optional[str] = None,
        skip_models: bool = False,
        max_models: Optional[int] = None,
        include_model_details: bool = True
    ):
        """
        初始化采集器

        Args:
            comfyui_path: ComfyUI 安装目录路径，如果不提供则自动检测
            server_url: ComfyUI 服务地址，用于获取运行时的节点信息
            models_root: 模型根目录（默认为 ComfyUI 根目录）
            skip_models: 是否跳过模型扫描
            max_models: 最多扫描的模型文件数量（None 表示不限制）
            include_model_details: 是否包含模型大小、修改时间等详细信息
        """
        self.comfyui_path = comfyui_path or self._detect_comfyui_path()
        self.server_url = server_url.rstrip('/')
        self.python_executable = sys.executable
        self.models_root = models_root or self.comfyui_path
        self.skip_models = skip_models
        self.max_models = max_models
        self.include_model_details = include_model_details

    def _detect_comfyui_path(self) -> Optional[str]:
        """自动检测 ComfyUI 安装目录"""
        # 尝试从当前脚本所在目录向上查找
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / "main.py").exists() and (parent / "comfy").exists():
                return str(parent)

        # 尝试常见安装位置
        common_paths = [
            "./ComfyUI",
            "../ComfyUI",
            os.path.expanduser("~/ComfyUI"),
            "/root/ComfyUI",
        ]
        for path in common_paths:
            p = Path(path)
            if p.exists() and (p / "main.py").exists():
                return str(p)

        return None

    def _read_file(self, file_path: Path) -> Optional[str]:
        """安全读取文件内容"""
        try:
            if file_path.exists():
                return file_path.read_text(encoding='utf-8')
        except Exception:
            pass
        return None

    def _run_command(self, cmd: List[str], cwd: Optional[str] = None, timeout: int = 10) -> Optional[str]:
        """执行命令并返回输出"""
        try:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _get_git_remote_url(self, repo_path: str) -> Optional[str]:
        """获取 Git 仓库的 remote.origin.url"""
        if not repo_path:
            return None
        # 检查是否为 Git 仓库
        git_dir = Path(repo_path) / ".git"
        if not git_dir.exists():
            return None
        # 获取 origin 的 URL
        url = self._run_command(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_path
        )
        return url if url else None

    def collect_backend_version(self) -> Dict[str, Any]:
        """采集后端版本信息"""
        result = {
            "comfyui_backend_version": None,
            "comfyui_commit_hash": None,
            "python_version": sys.version,
        }

        if not self.comfyui_path:
            return result

        # 从 pyproject.toml 读取版本
        pyproject_path = Path(self.comfyui_path) / "pyproject.toml"
        content = self._read_file(pyproject_path)
        if content:
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                result["comfyui_backend_version"] = match.group(1)

        # 获取 git commit hash
        git_head = Path(self.comfyui_path) / ".git" / "HEAD"
        if git_head.exists():
            head_content = self._read_file(git_head)
            if head_content and head_content.startswith("ref:"):
                ref_path = head_content.split(":")[1].strip()
                ref_file = Path(self.comfyui_path) / ".git" / ref_path
                commit = self._read_file(ref_file)
                if commit:
                    result["comfyui_commit_hash"] = commit.strip()[:40]

        # 备选: 使用 git 命令
        if not result["comfyui_commit_hash"] and self.comfyui_path:
            commit = self._run_command(["git", "rev-parse", "HEAD"], cwd=self.comfyui_path)
            if commit:
                result["comfyui_commit_hash"] = commit[:40]

        return result

    def collect_frontend_version(self) -> Dict[str, Any]:
        """采集前端版本信息"""
        result = {
            "comfyui_frontend_version": None,
            "comfyui_frontend_commit": None,
        }

        if not self.comfyui_path:
            return result

        # 检查前端目录
        frontend_dir = Path(self.comfyui_path) / "web"
        version_file = frontend_dir / "version.json"
        if version_file.exists():
            try:
                data = json.loads(version_file.read_text(encoding='utf-8'))
                result["comfyui_frontend_version"] = data.get("version")
            except Exception:
                pass

        # 尝试从 package.json 获取
        package_json = frontend_dir / "package.json"
        if package_json.exists():
            try:
                data = json.loads(package_json.read_text(encoding='utf-8'))
                result["comfyui_frontend_version"] = result["comfyui_frontend_version"] or data.get("version")
            except Exception:
                pass

        return result

    def collect_command_line_args(self) -> Dict[str, Any]:
        """采集命令行参数"""
        result = {
            "argv": sys.argv,
            "arg_count": len(sys.argv),
            "parsed_args": {},
        }

        # 尝试解析常见的命令行参数
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--port", type=int, default=8188)
        parser.add_argument("--host", type=str, default="127.0.0.1")
        parser.add_argument("--listen", action="store_true")
        parser.add_argument("--enable-cors-header", type=str)
        parser.add_argument("--output-directory", type=str)
        parser.add_argument("--input-directory", type=str)
        parser.add_argument("--auto-launch", action="store_true")
        parser.add_argument("--disable-auto-launch", action="store_true")
        parser.add_argument("--cuda-device", type=str)
        parser.add_argument("--dont-print-server", action="store_true")
        parser.add_argument("--quick-test-for-ci", action="store_true")
        parser.add_argument("--windows-standalone-build", action="store_true")
        parser.add_argument("--highvram", action="store_true")
        parser.add_argument("--normalvram", action="store_true")
        parser.add_argument("--lowvram", action="store_true")
        parser.add_argument("--novram", action="store_true")
        parser.add_argument("--cpu", action="store_true")
        parser.add_argument("--disable-smart-memory", action="store_true")
        parser.add_argument("--reserve-vram", type=float)
        parser.add_argument("--force-fp32", action="store_true")
        parser.add_argument("--force-fp16", action="store_true")
        parser.add_argument("--bf16-unet", action="store_true")
        parser.add_argument("--fp16-unet", action="store_true")
        parser.add_argument("--fp32-unet", action="store_true")
        parser.add_argument("--fp8-e4m3fn-unet", action="store_true")
        parser.add_argument("--fp8-e5m2-unet", action="store_true")
        parser.add_argument("--multi-user", action="store_true")
        parser.add_argument("--verbose", action="store_true")

        try:
            known, unknown = parser.parse_known_args()
            result["parsed_args"] = {
                k: v for k, v in vars(known).items() if v is not None
            }
            if unknown:
                result["unknown_args"] = unknown
        except SystemExit:
            pass

        return result

    def collect_environment_variables(self) -> Dict[str, Any]:
        """采集相关环境变量"""
        relevant_vars = [
            # CUDA 相关
            "CUDA_VISIBLE_DEVICES",
            "CUDA_DEVICE_ORDER",
            "CUDA_HOME",
            "CUBLAS_WORKSPACE_CONFIG",
            "PYTORCH_CUDA_ALLOC_CONF",
            "TORCH_CUDA_ARCH_LIST",
            # ComfyUI 相关
            "COMFYUI_PATH",
            "COMFYUI_FOLDER",
            "COMFYUI_DATA_DIR",
            "COMFYUI_EXTRA_MODELS_PATH",
            "COMFYUI_OUTPUT_DIRECTORY",
            "COMFYUI_INPUT_DIRECTORY",
            "COMFYUI_USER_DIRECTORY",
            # 网络相关
            "COMFYUI_HOST",
            "COMFYUI_PORT",
            "COMFYUI_DEFAULT_VIEW",
            # Python 相关
            "PYTHONPATH",
            "PYTHONUNBUFFERED",
            "VIRTUAL_ENV",
            "CONDA_PREFIX",
            "CONDA_DEFAULT_ENV",
            # 系统相关
            "PATH",
            "LD_LIBRARY_PATH",
            "https_proxy",
            "http_proxy",
            "no_proxy",
        ]

        result = {}
        for var in relevant_vars:
            value = os.environ.get(var)
            if value is not None:
                # 对 PATH 等长变量进行截断处理
                if var == "PATH" and len(value) > 500:
                    value = value[:500] + "...(truncated)"
                result[var] = value

        return result

    def collect_gpu_info(self) -> Dict[str, Any]:
        """采集 GPU 信息"""
        result = {
            "torch_available": torch is not None,
            "cuda_available": False,
            "cuda_version": None,
            "gpu_count": 0,
            "gpus": [],
            "nvidia_smi_info": None,
        }

        if torch is None:
            return result

        result["cuda_available"] = torch.cuda.is_available()

        if torch.cuda.is_available():
            result["cuda_version"] = torch.version.cuda
            result["gpu_count"] = torch.cuda.device_count()

            for i in range(result["gpu_count"]):
                gpu_info = {
                    "index": i,
                    "name": torch.cuda.get_device_name(i),
                    "capability": torch.cuda.get_device_capability(i),
                    "memory_allocated_mb": None,
                    "memory_reserved_mb": None,
                    "memory_total_mb": None,
                }

                # 获取内存信息
                try:
                    gpu_info["memory_allocated_mb"] = torch.cuda.memory_allocated(i) / (1024 ** 2)
                    gpu_info["memory_reserved_mb"] = torch.cuda.memory_reserved(i) / (1024 ** 2)
                    gpu_info["memory_total_mb"] = torch.cuda.get_device_properties(i).total_memory / (1024 ** 2)
                except Exception:
                    pass

                result["gpus"].append(gpu_info)

        # 尝试使用 nvidia-smi 获取更详细的信息
        nvidia_smi = self._run_command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,compute_cap", "--format=csv,noheader"])
        if nvidia_smi:
            result["nvidia_smi_info"] = nvidia_smi

        return result

    def collect_nodes_info_from_files(self) -> List[Dict[str, Any]]:
        """通过扫描 custom_nodes 目录采集节点信息，并获取 Git remote URL"""
        nodes = []

        if not self.comfyui_path:
            return nodes

        custom_nodes_dir = Path(self.comfyui_path) / "custom_nodes"
        if not custom_nodes_dir.exists():
            return nodes

        for node_dir in custom_nodes_dir.iterdir():
            if not node_dir.is_dir():
                continue

            node_info = {
                "name": node_dir.name,
                "path": str(node_dir),
                "version": None,
                "has_pyproject": False,
                "has_requirements": False,
                "git_remote_url": None,
                "git_commit": None,
            }

            # 检查 pyproject.toml
            pyproject_path = node_dir / "pyproject.toml"
            if pyproject_path.exists():
                node_info["has_pyproject"] = True
                content = self._read_file(pyproject_path)
                if content:
                    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        node_info["version"] = match.group(1)
                    else:
                        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
                        if match:
                            node_info["version"] = match.group(1)

            # 检查 __init__.py 中的版本
            if not node_info["version"]:
                init_file = node_dir / "__init__.py"
                content = self._read_file(init_file)
                if content:
                    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        node_info["version"] = match.group(1)

            # 检查 requirements.txt
            req_file = node_dir / "requirements.txt"
            if req_file.exists():
                node_info["has_requirements"] = True

            # 获取 Git 信息（remote URL 和 commit）
            git_dir = node_dir / ".git"
            if git_dir.exists():
                remote_url = self._get_git_remote_url(str(node_dir))
                if remote_url:
                    node_info["git_remote_url"] = remote_url
                commit = self._run_command(["git", "rev-parse", "--short", "HEAD"], cwd=str(node_dir))
                if commit:
                    node_info["git_commit"] = commit

            nodes.append(node_info)

        return nodes

    def collect_nodes_info_from_api(self) -> Optional[List[Dict[str, Any]]]:
        """通过 ComfyUI-Manager API 采集节点信息"""
        if requests is None:
            return None

        endpoints = [
            f"{self.server_url}/customnode/installed",
            f"{self.server_url}/customnode/getlist",
        ]

        for endpoint in endpoints:
            try:
                resp = requests.get(endpoint, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        return data.get("custom_nodes", data.get("nodes", []))
            except Exception:
                continue

        return None

    def collect_system_stats_from_api(self) -> Optional[Dict[str, Any]]:
        """通过 ComfyUI 系统 API 采集统计信息"""
        if requests is None:
            return None

        try:
            resp = requests.get(f"{self.server_url}/system_stats", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def collect_python_packages(self) -> List[Dict[str, str]]:
        """
        采集当前 Python 环境中已安装的包及其版本。
        优先使用 pip list --format=json，失败时使用 pkg_resources。
        """
        packages = []

        # 方法1: 使用 pip list (推荐)
        pip_cmd = [self.python_executable, "-m", "pip", "list", "--format=json"]
        output = self._run_command(pip_cmd, timeout=30)
        if output:
            try:
                data = json.loads(output)
                for pkg in data:
                    packages.append({
                        "name": pkg.get("name"),
                        "version": pkg.get("version")
                    })
                return packages
            except json.JSONDecodeError:
                pass

        # 方法2: 备选使用 pkg_resources (较慢，但无需 pip)
        try:
            import pkg_resources
            for dist in pkg_resources.working_set:
                packages.append({
                    "name": dist.project_name,
                    "version": dist.version
                })
        except ImportError:
            pass

        return packages

    def collect_models(self) -> Dict[str, Any]:
        """
        递归扫描 models_root 目录，收集所有模型文件信息。
        """
        result = {
            "root_path": str(self.models_root) if self.models_root else None,
            "total_count": 0,
            "files": [],
        }

        if not self.models_root or not Path(self.models_root).exists():
            result["error"] = f"Model root directory not found: {self.models_root}"
            return result

        root_path = Path(self.models_root)
        count = 0

        for dirpath, dirnames, filenames in os.walk(root_path):
            # 跳过隐藏目录（以 . 开头）和常见的非模型目录
            dirnames[:] = [d for d in dirnames if not d.startswith('.')]
            for filename in filenames:
                # 检查扩展名
                ext = Path(filename).suffix.lower()
                if ext not in self.MODEL_EXTENSIONS:
                    continue

                full_path = Path(dirpath) / filename
                rel_path = full_path.relative_to(root_path)

                model_info = {
                    "path": str(rel_path),
                    "full_path": str(full_path),
                }

                if self.include_model_details:
                    try:
                        stat = full_path.stat()
                        model_info["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
                        model_info["modified_time"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                    except Exception:
                        model_info["size_mb"] = None
                        model_info["modified_time"] = None

                result["files"].append(model_info)
                count += 1

                if self.max_models and count >= self.max_models:
                    break

            if self.max_models and count >= self.max_models:
                break

        result["total_count"] = count
        if self.max_models and count >= self.max_models:
            result["truncated"] = True

        return result

    def collect_all(self) -> Dict[str, Any]:
        """采集所有信息"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "comfyui_path": self.comfyui_path,
            "server_url": self.server_url,
            "backend": {},
            "frontend": {},
            "command_line_args": {},
            "environment_variables": {},
            "gpu": {},
            "custom_nodes": {},
            "python_packages": [],
            "models": {},
        }

        # 采集后端信息
        result["backend"] = self.collect_backend_version()

        # 采集前端信息
        result["frontend"] = self.collect_frontend_version()

        # 采集命令行参数
        result["command_line_args"] = self.collect_command_line_args()

        # 采集环境变量
        result["environment_variables"] = self.collect_environment_variables()

        # 采集 GPU 信息
        result["gpu"] = self.collect_gpu_info()

        # 采集节点信息
        nodes_from_files = self.collect_nodes_info_from_files()
        result["custom_nodes"]["from_files"] = nodes_from_files
        result["custom_nodes"]["count"] = len(nodes_from_files)

        # 尝试通过 API 获取节点信息
        nodes_from_api = self.collect_nodes_info_from_api()
        if nodes_from_api is not None:
            result["custom_nodes"]["from_api"] = nodes_from_api

        # 尝试通过系统 API 获取更多信息
        system_stats = self.collect_system_stats_from_api()
        if system_stats:
            result["system_stats_api"] = system_stats

        # 采集 Python 包列表
        result["python_packages"] = self.collect_python_packages()
        result["python_packages_count"] = len(result["python_packages"])

        # 采集模型文件（如果未跳过）
        if not self.skip_models:
            result["models"] = self.collect_models()

        return result


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ComfyUI Environment Info Collector")
    parser.add_argument(
        "--comfyui-path",
        type=str,
        help="ComfyUI installation directory path",
    )
    parser.add_argument(
        "--server-url",
        type=str,
        default="http://127.0.0.1:8188",
        help="ComfyUI server URL (for API calls)",
    )
    parser.add_argument(
        "--models-root",
        type=str,
        help="Root directory to scan for models (default: ComfyUI root directory)",
    )
    parser.add_argument(
        "--skip-models",
        action="store_true",
        help="Skip scanning for model files",
    )
    parser.add_argument(
        "--max-models",
        type=int,
        help="Maximum number of model files to list (default: no limit)",
    )
    parser.add_argument(
        "--no-model-details",
        action="store_true",
        help="Exclude file size and modification time from model info",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output",
    )

    args = parser.parse_args()

    # 创建采集器并采集信息
    collector = ComfyUIInfoCollector(
        comfyui_path=args.comfyui_path,
        server_url=args.server_url,
        models_root=args.models_root,
        skip_models=args.skip_models,
        max_models=args.max_models,
        include_model_details=not args.no_model_details,
    )
    info = collector.collect_all()

    # 输出结果
    output = json.dumps(info, indent=2 if args.pretty else None, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Info saved to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
