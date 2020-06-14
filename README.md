
#install as root

apt install udisks2 python3-serial
useradd octoprint
cp -a ./system/* /
mkdir -p /home/octoprint/src/minioctoprint
cp -a manage.py /home/octoprint/src/minioctoprint
cp -a ./main /home/octoprint/src/minioctoprint
systemctl enable minioctoprint
systemctl enable udiskmonitor
udevadm control -R

#now plug SKR mini with STM32F103RC_btt_512K_USB firmware
#upload file from cura with octoprint pugin, or prusha slicer
#check log
#journalctl -f -u minioctoprint@ttyACM0.service