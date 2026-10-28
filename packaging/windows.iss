; Built by scripts/build.py on Windows. Install for the current user, no admin prompt.
#ifndef AppVersion
  #error AppVersion must be supplied by the build script
#endif
#ifndef ProjectRoot
  #error ProjectRoot must be supplied by the build script
#endif

[Setup]
AppId={{75D0A2AF-5307-4C09-BCC8-098C5366DB9B}
AppName=S7 Studio
AppVersion={#AppVersion}
AppVerName=S7 Studio {#AppVersion}
AppPublisher=WendelYu
AppPublisherURL=https://github.com/WendelYu/S7Simulator
AppSupportURL=https://github.com/WendelYu/S7Simulator/issues
AppUpdatesURL=https://github.com/WendelYu/S7Simulator/releases
DefaultDirName={localappdata}\Programs\S7 Studio
DefaultGroupName=S7 Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ProjectRoot}\dist
OutputBaseFilename=S7Studio-v{#AppVersion}-windows-x64-setup
SetupIconFile={#ProjectRoot}\build\icons\S7Studio.ico
UninstallDisplayIcon={app}\S7 Studio.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#ProjectRoot}\dist\S7 Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\S7 Studio"; Filename: "{app}\S7 Studio.exe"
Name: "{autodesktop}\S7 Studio"; Filename: "{app}\S7 Studio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\S7 Studio.exe"; Description: "{cm:LaunchProgram,S7 Studio}"; Flags: nowait postinstall skipifsilent
