id
echo ===KFD-TEST===
python3 -c "open('/dev/kfd','rb'); print('KFD ACCESS OK')" 2>&1 | tail -2
echo ===OPT-BANKSY===
ls /opt/banksy
echo ===RUNNING===
ps -eo comm,pcpu --sort=-pcpu | head -8
ss -lntp 2>/dev/null | head -12
