# 说明
采集comfyui容器运行的环境中comfyui相关信息，包括
* comfyui命令参数
* comfyui版本
* custom node节点以及版本
* 安装的python包
* 安装的模型


# 使用示例
```bash
# 扫描默认路径（/root/ComfyUI 或自动检测到的路径）
python comfyui_info_collector.py --pretty

# 保存到文件
python comfyui_info_collector.py --pretty --output env_info.json


# 指定不同的模型根目录，最多列出 100 个模型
python comfyui_info_collector.py --models-root /data/models --max-models 100 --pretty

# 只列出模型路径，不包含大小和时间
python comfyui_info_collector.py --no-model-details --pretty

# 跳过模型扫描
python comfyui_info_collector.py --skip-models --output info.json
```