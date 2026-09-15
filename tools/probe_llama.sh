echo ===LLAMA-SERVER-BINARY===
ps -eo pid,comm,args --sort=-pcpu | grep -m1 llama-server | cut -c1-240
echo
echo ===BUILD-TYPE===
BIN=$(ls -1 /opt/banksy/llama.cpp/build/bin/llama-server 2>/dev/null || which llama-server)
echo "binary: $BIN"
ldd "$BIN" 2>/dev/null | grep -i -E 'hip|rocm|amdhip|rocblas' || echo "NO HIP/ROCm LIBS LINKED -> CPU-only build"
echo
echo ===VERSION-BANNER===
"$BIN" --version 2>&1 | head -5
echo
echo ===ROCM-PRESENT===
ls -d /opt/rocm* 2>/dev/null || echo "no /opt/rocm"
dpkg -l 2>/dev/null | grep -c -i rocm
echo
echo ===GPU-BUSY===
cat /sys/class/drm/card1/device/gpu_busy_percent 2>/dev/null || echo "no gpu_busy_percent"
