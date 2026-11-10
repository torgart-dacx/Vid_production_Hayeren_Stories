#!/bin/sh
# Скачивает мужские голоса Piper в ./voices (нужен доступ к huggingface.co и us.aws.cdn.hf.co)
set -e
B=https://huggingface.co/rhasspy/piper-voices/resolve/main
mkdir -p voices && cd voices
for f in ru/ru_RU/denis/medium/ru_RU-denis-medium ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium \
         es/es_MX/claude/high/es_MX-claude-high es/es_ES/davefx/medium/es_ES-davefx-medium; do
  for e in .onnx .onnx.json; do curl -fL -O "$B/$f$e"; done
done
