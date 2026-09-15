cd /opt/banksy/llama.cpp || exit 1
echo "=== existing bench dir ==="
ls -la /opt/banksy/models/bench 2>/dev/null | head -10
echo
echo "=== starting vulkan build (separate dir, CPU build untouched) ==="
rm -f /opt/banksy/vulkan_build.log
nohup bash -c '
  cd /opt/banksy/llama.cpp
  cmake -B build-vulkan -DGGML_VULKAN=ON -DGGML_NATIVE=ON -DCMAKE_BUILD_TYPE=Release -G Ninja
  cmake --build build-vulkan --config Release -j 32
  echo "BUILD_EXIT=$?"
' > /opt/banksy/vulkan_build.log 2>&1 &
echo "launched pid $!"
sleep 20
echo "=== first 25 lines ==="
head -25 /opt/banksy/vulkan_build.log
