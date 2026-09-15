M=/opt/banksy/models/bench/Qwen3-4B-Instruct-2507.gguf
rm -f /opt/banksy/bench_vulkan.log
nohup bash -c "
  echo '=== VULKAN (GPU, -ngl 99) ==='
  /opt/banksy/llama.cpp/build-vulkan/bin/llama-bench -m $M -ngl 99 -p 512 -n 128 -r 2
  echo
  echo '=== CPU (-ngl 0) ==='
  /opt/banksy/llama.cpp/build-vulkan/bin/llama-bench -m $M -ngl 0 -p 512 -n 128 -r 2
  echo BENCH_EXIT=\$?
" > /opt/banksy/bench_vulkan.log 2>&1 &
echo "launched pid $!"
sleep 45
echo "=== progress ==="
tail -20 /opt/banksy/bench_vulkan.log
