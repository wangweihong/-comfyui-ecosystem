#!/bin/bash


docker run -it  \
  --name comfyui \
  --gpus 1 \
  -p 8188:8188 \
  -v "$(pwd)"/storage:/root \
  -v  /media/wwhvw/A63032EE3032C5591/comfyui-docker/storage-models/models:/root/ComfyUI/models \
  -v /media/wwhvw/A63032EE3032C5591/comfyui-docker/storage-models/hf-hub:/root/.cache/huggingface/hub \
  -v /media/wwhvw/A63032EE3032C5591/comfyui-docker/storage-models/torch-hub:/root/.cache/torch/hub \
  -v "$(pwd)"/storage-user/input:/root/ComfyUI/input \
  -v "$(pwd)"/storage-user/output:/root/ComfyUI/output \
  -v /home/wwhvw/codespace/comfyui-ecosystem/workflows:/root/ComfyUI/user/default/workflows \
  -v /home/wwhvw/codespace/comfyui-ecosystem/subgraphs:/root/ComfyUI/user/default/subgraphs \
  --entrypoint bash \
  -e CLI_ARGS="--disable-xformers" \
  -e HF_TOKEN="https://hf-mirror.com" \
  registry.cn-hangzhou.aliyuncs.com/eazycloud/comfyui-boot:cu128-megapak


# cli-args参数： --disable-smart-memory： 这个参数可以让comfyui将显存的数据大量搬运到内存。
#               --disable-xformers: 不设置某些模型会出现花图