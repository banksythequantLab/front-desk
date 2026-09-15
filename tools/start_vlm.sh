M=/opt/banksy/models/vlm/Qwen3VL-30B-A3B-Instruct-Q4_K_M.gguf
P=/opt/banksy/models/vlm/mmproj-Qwen3VL-30B-A3B-Instruct-F16.gguf
BIN=/opt/banksy/llama.cpp/build-vulkan/bin/llama-server

echo "=== groups in this session ==="
id -nG

echo "=== ports already listening ==="
ss -lnt 2>/dev/null | awk 'NR>1 {print $4}' | sort -u | head -12

echo "=== launching vision server on :8081 ==="
rm -f /opt/banksy/vlm_server.log
nohup "$BIN" -m "$M" --mmproj "$P" -ngl 99 \
  --host 0.0.0.0 --port 8081 -c 8192 -t 16 \
  > /opt/banksy/vlm_server.log 2>&1 &
echo "launched pid $!"
sleep 40
echo "=== load progress ==="
grep -i -E 'vulkan|offload|mmproj|listening|error' /opt/banksy/vlm_server.log | tail -14
