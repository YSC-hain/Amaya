---------------- Shell 安装完成 ---------------- 
[2025-07-31 17:11:43]:  
[2025-07-31 17:11:43]: 启动 Napcat (需要图形环境或 Xvfb): 
[2025-07-31 17:11:43]:   sudo xvfb-run -a qq --no-sandbox 
[2025-07-31 17:11:43]:  
[2025-07-31 17:11:43]: 后台运行 Napcat (使用 screen)(请使用 root 账户): 
[2025-07-31 17:11:43]:   启动: screen -dmS napcat bash -c "xvfb-run -a qq --no-sandbox" 
[2025-07-31 17:11:43]:   带账号启动: screen -dmS napcat bash -c "xvfb-run -a qq --no-sandbox -q 1312778474" 
[2025-07-31 17:11:43]:   附加到会话: screen -r napcat (按 Ctrl+A 然后按 D 分离) 
[2025-07-31 17:11:43]:   停止会话: screen -S napcat -X quit 
[2025-07-31 17:11:43]:  
[2025-07-31 17:11:43]: Napcat 相关信息: 
[2025-07-31 17:11:43]:   安装位置: /opt/QQ/resources/app/app_launcher/napcat 
[2025-07-31 17:11:43]:   WebUI Token: 查看 /opt/QQ/resources/app/app_launcher/napcat/config/webui.json 文件获取 
[2025-07-31 17:11:43]:  
[2025-07-31 17:11:43]: TUI-CLI 工具用法 (napcat): 
[2025-07-31 17:11:43]:   启动: sudo napcat 
[2025-07-31 17:11:43]: --------------------------------------------------
[2025-07-31 17:11:43]: Shell 安装流程完成。 