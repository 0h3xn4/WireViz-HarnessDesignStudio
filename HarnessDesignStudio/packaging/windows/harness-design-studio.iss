; Inno Setup script of the Windows installer (docs/RELEASE.md, D-149).
; Built by tools/build_windows.py, which passes the values below with /D:
;   AppVersion     the version of the tool (1.2.0)
;   NumericVersion four numbers for the version resource (1.2.0.0)
;   SourceDir      the finished program folder (dist/harness-design-studio)
;   OutputDir      where the setup program is written (dist)
;   IconFile       the .ico of the logo
; Per-user install: no administrator rights, nothing written outside the user's own folders and
; HKCU, no network access at install or run time. The programs are not signed unless the build had
; a certificate (docs/RELEASE.md, Signing).

#ifndef AppVersion
  #error AppVersion is not defined: build with tools/build_windows.py
#endif

#define AppName "Harness Design Studio"

[Setup]
AppId={{6E1F0C52-3B8A-4D7E-9C41-A5D2B7F84E10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Harness Design Studio
VersionInfoVersion={#NumericVersion}
VersionInfoDescription={#AppName} setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=harness-design-studio-{#AppVersion}-windows-x86_64-setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\harness-design-studio-gui.exe
UninstallDisplayName={#AppName}
InfoBeforeFile={#SourceDir}\README-windows.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
CloseApplications=no
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}\{#AppName}"; Filename: "{app}\harness-design-studio-gui.exe"; Comment: "Design spacecraft wiring harnesses (offline)"
Name: "{autoprograms}\{#AppName}\Read me and licences"; Filename: "{app}\README-windows.txt"
Name: "{autoprograms}\{#AppName}\Uninstall {#AppName}"; Filename: "{uninstallexe}"

[Code]
// The command line tool (cli\harness-design-studio.exe, cli\harness.exe) and the editor
// (harness-design-studio-gui.exe) are found by name in a new terminal: both folders go on the PATH
// of this user (HKCU\Environment) and come off again when the program is removed.

function SamePath(const A, B: string): Boolean;
begin
  Result := CompareText(RemoveBackslash(A), RemoveBackslash(B)) = 0;
end;

function HasPathEntry(const Paths, Entry: string): Boolean;
var
  Rest, Item: string;
  P: Integer;
begin
  Result := False;
  Rest := Paths;
  while Rest <> '' do
  begin
    P := Pos(';', Rest);
    if P = 0 then
    begin
      Item := Rest;
      Rest := '';
    end
    else
    begin
      Item := Copy(Rest, 1, P - 1);
      Rest := Copy(Rest, P + 1, Length(Rest));
    end;
    if (Item <> '') and SamePath(Item, Entry) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function WithoutPathEntry(const Paths, Entry: string): string;
var
  Rest, Item: string;
  P: Integer;
begin
  Result := '';
  Rest := Paths;
  while Rest <> '' do
  begin
    P := Pos(';', Rest);
    if P = 0 then
    begin
      Item := Rest;
      Rest := '';
    end
    else
    begin
      Item := Copy(Rest, 1, P - 1);
      Rest := Copy(Rest, P + 1, Length(Rest));
    end;
    if (Item <> '') and not SamePath(Item, Entry) then
    begin
      if Result <> '' then
        Result := Result + ';';
      Result := Result + Item;
    end;
  end;
end;

procedure AddToUserPath(const Entry: string);
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) then
    Paths := '';
  if HasPathEntry(Paths, Entry) then
    Exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then
    Paths := Paths + ';';
  RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Paths + Entry);
end;

procedure RemoveFromUserPath(const Entry: string);
var
  Paths: string;
begin
  if RegQueryStringValue(HKCU, 'Environment', 'Path', Paths) and HasPathEntry(Paths, Entry) then
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', WithoutPathEntry(Paths, Entry));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    AddToUserPath(ExpandConstant('{app}\cli'));
    AddToUserPath(ExpandConstant('{app}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemoveFromUserPath(ExpandConstant('{app}\cli'));
    RemoveFromUserPath(ExpandConstant('{app}'));
  end;
end;
