; Установщик Free AI Reader (FAIR) — Inno Setup 6
; Собирается командой:
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" build_installer\fair.iss
; Перед этим: pyinstaller build_installer\fair.spec --noconfirm --distpath dist_installer

#define AppName "Free AI Reader"
#define AppShortName "FAIR"
#define AppVersion "1.2"
#define AppPublisher "Yaroslav Khmelev"
#define AppExe "FAIR.exe"

[Setup]
AppId={{8D2C4B71-6A3E-4F52-9C1D-2E7A5B0F9C34}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL=https://github.com/yaroslav-softcode/FAIR
DefaultDirName={autopf}\Free AI Reader
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
; без UAC у обычного пользователя, но можно поставить «для всех» из диалога
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
Source: "..\dist_installer\FAIR\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\THIRD-PARTY.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*.log"

[Code]
{ Папка данных: настройки, скачанные модели, голоса — рядом с профилем пользователя }
function DataDir(): String;
begin
  Result := ExpandConstant('{localappdata}\FAIR');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Answer: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DirExists(DataDir()) then
    begin
      Answer := MsgBox('Удалить настройки и скачанные модели?' + #13#10 +
                       DataDir() + #13#10#13#10 +
                       'Модель Gemma весит около 5 ГБ — если планируете ставить FAIR снова, ' +
                       'лучше оставить.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2);
      if Answer = IDYES then
        DelTree(DataDir(), True, True, True);
    end;
  end;
end;
