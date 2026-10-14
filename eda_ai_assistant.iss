; -*- coding: utf-8 -*-
; EDA AI 智能助手 — Inno Setup 装机脚本（onedir 分发的安装器形态）
;
; 2026-10-14 分发拍板配套：onefile 无签名不可分发 ⇒ onedir（zip 或本装机包）。
; 版本号唯一来源 src/constants.py 的 APP_VERSION，由 build.bat 经
; /DAPP_VERSION= 传入（此处默认值仅兜底，勿双头维护）。
;
; 编译器口径（2026-10-14 乱码修复批）：需 Inno Setup 6+（Unicode 版），本文件保存为
; UTF-8 带 BOM。5.x 是 ANSI 编译器，会把中文按 GBK 误读，快捷方式/开始菜单/卸载
; 注册表全部乱码（装机验证实测）；本机旧 5.5.8 已卸载。
;   - {pf} 在 6.x 仍有效（admin 下指 Program Files (x86)），沿用不动
;   - 向导默认英文；如需中文向导，6.x 自带 ChineseSimplified.isl，可在 [Languages]
;     段启用（留待下次出包验证）

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
