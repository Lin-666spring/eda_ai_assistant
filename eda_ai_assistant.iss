; -*- coding: utf-8 -*-
; EDA AI 智能助手 — Inno Setup 装机脚本（onedir 分发的安装器形态）
;
; 2026-10-14 分发拍板配套：onefile 无签名不可分发 ⇒ onedir（zip 或本装机包）。
; 版本号唯一来源 src/constants.py 的 APP_VERSION，由 build.bat 经
; /DAPP_VERSION= 传入（此处默认值仅兜底，勿双头维护）。
;
; 兼容 Inno Setup 5.5.8（本机无 VPN 时可从 files.jrsoftware.org 直连安装）：
;   - 不用 {autopf}（6.x 才有），用 {pf}
;   - 不用 PrivilegesRequiredOverridesAllowed / CloseApplications（6.x 才有）
;   - 中文向导翻译为非官方语言包，官方 5.5.8 不带，向导保持英文

#ifndef APP_VERSION
#define APP_VERSION "0.8.0"
#endif

#define MyAppName "EDA AI Assistant"
#define MyAppNameCn "EDA AI 智能助手"
#define MyAppExeName "EDA_AI_Assistant.exe"

[Setup]
AppId={{7E4A2C19-93B6-4F5D-8A21-56C0B4D3E8F2}
AppName={#MyAppNameCn}
AppVersion={#APP_VERSION}
AppPublisher=智绘PCB 项目组
DefaultDirName={pf}\EDA_AI_Assistant
DefaultGroupName={#MyAppNameCn}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=dist
OutputBaseFilename=EDA_AI_Assistant_v{#APP_VERSION}_setup
Compression=lzma2/normal
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; 整个 onedir 产物（exe + _internal）原样落地
Source: "dist\EDA_AI_Assistant\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppNameCn}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppNameCn}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppNameCn}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppNameCn}}"; Flags: nowait postinstall skipifsilent
