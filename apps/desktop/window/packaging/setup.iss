#ifndef BundleDir
  #error BundleDir must point to the verified PyInstaller bundle.
#endif
#ifndef OutputDirectory
  #error OutputDirectory must be supplied by the build script.
#endif
#ifndef AppVersion
  #define AppVersion "0.4.0"
#endif

[Setup]
AppId={{E2A673FA-FCFD-4696-8E08-125D5E91F5AF}
AppName=Stream Chat
AppVersion={#AppVersion}
AppPublisher=Stream Chat
DefaultDirName={localappdata}\Programs\StreamChat
DefaultGroupName=Stream Chat
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDirectory}
OutputBaseFilename=StreamChat-Setup-{#AppVersion}-x64
UninstallDisplayIcon={app}\StreamChat.exe
SetupIconFile=..\..\..\assets\app.ico
WizardSmallImageFile=..\..\..\assets\app-256.png
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Stream Chat"; Filename: "{app}\StreamChat.exe"; WorkingDir: "{app}"; IconFilename: "{app}\StreamChat.exe"; IconIndex: 0; AppUserModelID: "StreamChat.Desktop"
Name: "{autodesktop}\Stream Chat"; Filename: "{app}\StreamChat.exe"; WorkingDir: "{app}"; IconFilename: "{app}\StreamChat.exe"; IconIndex: 0; AppUserModelID: "StreamChat.Desktop"; Tasks: desktopicon

[Run]
Filename: "{app}\StreamChat.exe"; Description: "{cm:LaunchProgram,Stream Chat}"; Flags: nowait postinstall skipifsilent

; No UninstallDelete: user connection settings and chat preferences are retained.
