echo "=== larger Qwen3-VL variants ==="
curl -s "https://huggingface.co/api/models?search=Qwen3-VL-30B&limit=6" | python3 -c "
import sys,json
for m in json.load(sys.stdin): print(' ', m['id'])
" 2>/dev/null
curl -s "https://huggingface.co/api/models?search=Qwen3-VL-32B&limit=6" | python3 -c "
import sys,json
for m in json.load(sys.stdin): print(' ', m['id'])
" 2>/dev/null
echo
echo "=== files in Qwen/Qwen3-VL-8B-Instruct-GGUF ==="
curl -s "https://huggingface.co/api/models/Qwen/Qwen3-VL-8B-Instruct-GGUF" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for f in d.get('siblings',[]):
    n=f['rfilename']
    if n.endswith('.gguf'): print(' ', n)
" 2>/dev/null
