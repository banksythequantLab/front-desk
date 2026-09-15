REPO=Qwen/Qwen3-VL-30B-A3B-Instruct-GGUF
DEST=/opt/banksy/models/vlm
mkdir -p $DEST
echo "=== available files ==="
curl -s "https://huggingface.co/api/models/$REPO" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for f in d.get('siblings',[]):
    n=f['rfilename']
    if n.endswith('.gguf'): print(n)
" > /tmp/vlm_files.txt 2>/dev/null
cat /tmp/vlm_files.txt

MODEL=$(grep -i -E 'Q4_K_M' /tmp/vlm_files.txt | grep -v -i mmproj | head -1)
MMPROJ=$(grep -i mmproj /tmp/vlm_files.txt | grep -i -E 'f16|F16' | head -1)
[ -z "$MMPROJ" ] && MMPROJ=$(grep -i mmproj /tmp/vlm_files.txt | head -1)
echo
echo "selected model : $MODEL"
echo "selected mmproj: $MMPROJ"

if [ -z "$MODEL" ] || [ -z "$MMPROJ" ]; then echo "SELECTION FAILED - stopping"; exit 1; fi

rm -f /opt/banksy/vlm_dl.log
nohup bash -c "
  cd $DEST
  curl -L --fail -C - -o '$(basename $MODEL)'  'https://huggingface.co/$REPO/resolve/main/$MODEL'
  echo MODEL_EXIT=\$?
  curl -L --fail -C - -o '$(basename $MMPROJ)' 'https://huggingface.co/$REPO/resolve/main/$MMPROJ'
  echo MMPROJ_EXIT=\$?
  ls -lh $DEST
" > /opt/banksy/vlm_dl.log 2>&1 &
echo "launched pid $!"
sleep 25
echo "=== progress ==="
tail -c 600 /opt/banksy/vlm_dl.log
