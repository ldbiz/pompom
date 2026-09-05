#define MyAppName "pompom"
#define MyAppVersion "1.0.1"
#define MyAppExeName "pompom.exe"

[Setup]
AppId={{19A5977C-7028-4F36-9A51-67B68ED028C4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=ldbiz
DefaultDirName={localappdata}\Programs\pompom
DefaultGroupName=pompom
DisableDirPage=no
DisableProgramGroupPage=no
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=pompom-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "autostart"; Description: "Start pompom when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\pompom\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\pompom"; Filename: "{app}\{#MyAppExeName}"
Name: "{userdesktop}\pompom"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\pompom"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch pompom"; Flags: nowait postinstall skipifsilent

[Code]
const
  SettingsSection = 'General';
  AutostartSetting = 'start_with_windows';

procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsFile := ExpandConstant('{userappdata}\pompom\pompom.ini');
    ForceDirectories(ExtractFileDir(SettingsFile));
    if WizardIsTaskSelected('autostart') then
      SetIniString(SettingsSection, AutostartSetting, 'true', SettingsFile)
    else
    begin
      DeleteFile(ExpandConstant('{userstartup}\pompom.lnk'));
      SetIniString(SettingsSection, AutostartSetting, 'false', SettingsFile);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    DeleteFile(ExpandConstant('{userstartup}\pompom.lnk'));
    SetIniString(
      SettingsSection,
      AutostartSetting,
      'false',
      ExpandConstant('{userappdata}\pompom\pompom.ini')
    );
  end;
end;
