; YouTube İndirici - Inno Setup kurulum betiği
; Derleme: önce scripts/fetch_ffmpeg.py ve PyInstaller ile dist/ klasörünü oluştur, sonra bu dosyayı ISCC ile derle.

#define AppName "YouTube İndirici"
#define AppVersion "1.0.0"
#define AppPublisher "Miraç Deprem"
#define AppURL "https://github.com/MrcDprm/youtube-downloader"
#define AppExeName "YouTubeDownloader.exe"

[Setup]
AppId={{11DE01D4-45BE-4C00-AB6D-60FCD657431A}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
DefaultDirName={autopf}\YouTubeDownloader
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=YouTubeDownloader-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\YouTubeDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
