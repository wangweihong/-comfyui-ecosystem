#!/bin/bash

sudo docker run -it  \
  --name comfyui \
  --gpus 1 \
  -p 8188:8188 \
  -v "$(pwd)"/storage:/root \
  -v "$(pwd)"/storage-models/models:/root/ComfyUI/models \
  -v "$(pwd)"/storage-models/hf-hub:/root/.cache/huggingface/hub \
  -v "$(pwd)"/storage-models/torch-hub:/root/.cache/torch/hub \
  -v "$(pwd)"/storage-user/input:/root/ComfyUI/input \
  -v "$(pwd)"/storage-user/output:/root/ComfyUI/output \
  -v "$(pwd)"/storage-user/workflows:/root/ComfyUI/user/default/workflows \
  -v "$(pwd)"/storage-user/subgraphs:/root/ComfyUI/user/default/subgraphs \
  --entrypoint bash \
  -e CLI_ARGS="--disable-xformers" \
  registry.cn-hangzhou.aliyuncs.com/eazycloud/comfyui-boot:cu128-megapak
