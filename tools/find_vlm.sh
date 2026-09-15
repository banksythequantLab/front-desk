echo "=== Qwen3-VL GGUF ==="
curl -s "https://huggingface.co/api/models?search=Qwen3-VL-GGUF&sort=downloads&direction=-1&limit=8" | python3 -c "
import sys,json
for m in json.load(sys.stdin):
    print(f\"{m['downloads']:>9}  {m['id']}\")
" 2>/dev/null || echo "query failed"
echo
echo "=== Qwen2.5-VL GGUF ==="
curl -s "https://huggingface.co/api/models?search=Qwen2.5-VL-GGUF&sort=downloads&direction=-1&limit=8" | python3 -c "
import sys,json
for m in json.load(sys.stdin):
    print(f\"{m['downloads']:>9}  {m['id']}\")
" 2>/dev/null || echo "query failed"
echo
echo "=== llama.cpp vision support ==="
ls /opt/banksy/llama.cpp/build-vulkan/bin/ | grep -i -E 'mtmd|llava|qwen2vl' || echo "no mtmd binary"
/opt/banksy/llama.cpp/build-vulkan/bin/llama-server --help 2>&1 | grep -i -E 'mmproj|no-mmproj' | head -4
echo
echo "=== hf cli ==="
which hf huggingface-cli 2>/dev/null || echo "no hf cli"
df -h /opt/banksy | tail -1
