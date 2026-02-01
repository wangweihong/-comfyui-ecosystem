#!/usr/bin/env bash
set -e

yq() { python3 - <<EOF
import yaml,sys
print(yaml.safe_load(open("$1"))["$2"]["version"])
EOF
}

sync_repo () {
  local name=$1
  local repo=$2
  local version=$3
  local dir=/workspace/$name

  [ "$version" = "null" ] && return

  if [ ! -d "$dir/.git" ]; then
    git clone "$repo" "$dir"
  fi

  cd "$dir"
  git fetch --all

  if [ "$version" = "latest" ]; then
    git checkout $(git rev-parse origin/HEAD)
  else
    git checkout "$version"
  fi
}

sync_repo ComfyUI \
  "$(yq /manifests/comfyui.yaml comfyui.repo)" \
  "$(yq /manifests/comfyui.yaml comfyui.version)"

sync_repo ComfyUI-Manager \
  "$(yq /manifests/comfyui.yaml manager.repo)" \
  "$(yq /manifests/comfyui.yaml manager.version)"
