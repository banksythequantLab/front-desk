echo ===VULKAN===
which vulkaninfo glslc 2>/dev/null || echo "no vulkan tools"
ls /usr/lib/x86_64-linux-gnu/libvulkan.so* 2>/dev/null || echo "no libvulkan"
vulkaninfo --summary 2>/dev/null | grep -i -E 'deviceName|driverName|apiVersion' | head -6
echo
echo ===MESA===
dpkg -l 2>/dev/null | grep -E 'mesa-vulkan|libvulkan' | awk '{print $2, $3}' | head -5
echo
echo ===BUILD-TOOLS===
which cmake ninja gcc g++ 2>/dev/null
cmake --version 2>/dev/null | head -1
echo
echo ===LLAMA-REPO===
cd /opt/banksy/llama.cpp 2>/dev/null && git log --oneline -1 && du -sh . 2>/dev/null
echo
echo ===MODELS===
ls -lh /opt/banksy/models 2>/dev/null | head -15
echo
echo ===SERVICE===
systemctl is-active llama-server 2>/dev/null; systemctl is-enabled llama-server 2>/dev/null
