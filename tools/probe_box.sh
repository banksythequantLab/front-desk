echo ===BLOCK===
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | head -20
echo ===VG===
vgs 2>/dev/null || echo need-sudo
echo ===LV===
lvs 2>/dev/null || echo need-sudo
echo ===GPU===
cat /sys/class/drm/card1/device/product_name 2>/dev/null
lspci 2>/dev/null | grep -i -E 'vga|display' | head -3
echo ===KFD===
ls -l /dev/kfd
groups
echo ===SUDO===
sudo -n true 2>&1 && echo passwordless-sudo-OK || echo sudo-needs-password
