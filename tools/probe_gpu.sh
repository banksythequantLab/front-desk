echo ===DATA-DISK===
df -h /opt/banksy | tail -1
ls -la /opt/banksy | head -10
echo ===KFD-ACL===
getfacl /dev/kfd 2>/dev/null | grep -v '^#'
echo ===DRI-ACL===
getfacl /dev/dri/card1 2>/dev/null | grep -v '^#'
echo ===AMDGPU===
dmesg 2>/dev/null | grep -i amdgpu | tail -5 || sudo dmesg | grep -i amdgpu | tail -5
echo ===VRAM===
cat /sys/class/drm/card1/device/mem_info_vram_total 2>/dev/null
echo ===OS===
lsb_release -d 2>/dev/null; cat /etc/os-release | grep PRETTY
