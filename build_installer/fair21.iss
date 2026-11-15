; Установщик FAIR 2.1 — ставится РЯДОМ с 1.11, отдельный ярлык и своя папка данных.
; Собирается командой:
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" build_installer\fair21.iss
; Перед этим: pyinstaller build_installer\fair21.spec --noconfirm --distpath dist_installer

#define AppName "Free AI Reader 2.1"
#define AppShortName "FAIR 2.1"
#define AppVersion "2.1"
#define AppPublisher "Yaroslav Khmelev"
#define AppExe "FAIR 2.1.exe"

[Setup]
; ❗ СВОЙ AppId: с общим идентификатором установщик 2.1 считался бы обновлением 1.11
AppId={{A6F1C2D3-7B4E-4C81-9E52-3D8B1A7C6F20}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL=https://github.com/yaroslav-softcode/FAIR
DefaultDirName={autopf}\Free AI Reader 2.1
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=FAIR-Setup-{#AppVersion}
SetupIconFile=..\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
InfoAfterFile=..\THIRD-PARTY.md
MinVersion=10.0

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "..\dist_installer\FAIR21\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD-PARTY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\MCP.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppShortName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*.log"

[Code]
{ Своя папка данных: настройки и библиотека 2.1. Модели лежат в общей папке 1.11
  (%LOCALAPPDATA%\FAIR) — их удаление не предлагаем: ими пользуются обе версии. }
function DataDir(): String;
begin
  Result := ExpandConstant('{localappdata}\FAIR21');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Answer: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DirExists(DataDir()) then
    begin
      Answer := MsgBox('Удалить настройки и библиотеку версии 2.1?' + #13#10 +
                       DataDir() + #13#10#13#10 +
                       'Модели и голоса лежат в общей папке FAIR — они останутся.', mbConfirmation,
                       MB_YESNO or MB_DEFBUTTON2);
      if Answer = IDYES then
        DelTree(DataDir(), True, True, True);
    end;
  end;
end;
