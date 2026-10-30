#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <objbase.h>
#include <stdio.h>

static BOOL extract(HINSTANCE instance, WORD id, const wchar_t *path) {
    HRSRC res = FindResourceW(instance, MAKEINTRESOURCEW(id), RT_RCDATA);
    if (!res) return FALSE;
    const BYTE *data = (const BYTE *)LockResource(LoadResource(instance, res));
    DWORD size = SizeofResource(instance, res), length = 0, written = 0;
    if (!data || size < 12) return FALSE;
    CopyMemory(&length, data + 8, 4);
    if (!length || length > size - 12) return FALSE;
    HANDLE file = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (file == INVALID_HANDLE_VALUE) return FALSE;
    BOOL ok = WriteFile(file, data + 12, length, &written, NULL) && written == length;
    CloseHandle(file);
    return ok;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR args, int show) {
    (void)previous; (void)args; (void)show;
    wchar_t temp[MAX_PATH], root[MAX_PATH], gui[MAX_PATH], core[MAX_PATH], icon[MAX_PATH];
    wchar_t system[MAX_PATH], command[4096], guid[40];
    GUID unique;
    DWORD result = 1;
    PROCESS_INFORMATION process = {0};
    STARTUPINFOW startup = {0};
    startup.cb = sizeof(startup);
    if (!GetTempPathW(MAX_PATH, temp) || FAILED(CoCreateGuid(&unique))) goto fail;
    StringFromGUID2(&unique, guid, 40);
    if (swprintf(root, MAX_PATH, L"%lsBarcodeSetup-%ls", temp, guid) < 0 || !CreateDirectoryW(root, NULL)) goto fail;
    swprintf(gui, MAX_PATH, L"%ls\\Setup-GUI.ps1", root);
    swprintf(core, MAX_PATH, L"%ls\\Setup-Barcode.cmd", root);
    swprintf(icon, MAX_PATH, L"%ls\\BarcodeStudio.ico", root);
    if (!extract(instance, 101, gui) || !extract(instance, 102, core) || !extract(instance, 103, icon)) goto cleanup;
    SetEnvironmentVariableW(L"BARCODE_SETUP_GUI_ROOT", root);
    SetEnvironmentVariableW(L"BARCODE_SETUP_FILE", core);
    SetEnvironmentVariableW(L"BARCODE_SETUP_MODE", L"install");
    if (!GetSystemDirectoryW(system, MAX_PATH)) goto cleanup;
    swprintf(command, 4096, L"\"%ls\\WindowsPowerShell\\v1.0\\powershell.exe\" -NoLogo -NoProfile -STA -Command \"$ErrorActionPreference='Stop';try{&([scriptblock]::Create([IO.File]::ReadAllText((Join-Path $env:BARCODE_SETUP_GUI_ROOT 'Setup-GUI.ps1'))))}catch{Add-Type -AssemblyName System.Windows.Forms;[Windows.Forms.MessageBox]::Show($_.Exception.Message,'Barcode Studio Setup')|Out-Null;exit 1}\"", system);
    if (!CreateProcessW(NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, root, &startup, &process)) goto cleanup;
    WaitForSingleObject(process.hProcess, INFINITE);
    GetExitCodeProcess(process.hProcess, &result);
    CloseHandle(process.hThread); CloseHandle(process.hProcess);
cleanup:
    DeleteFileW(gui); DeleteFileW(core); DeleteFileW(icon); RemoveDirectoryW(root);
    if (result == 0) return 0;
fail:
    MessageBoxW(NULL, L"Setup did not complete. Keep the setup error/log for support. Windows 10/11 x64 and Windows PowerShell are required.", L"Barcode Studio Setup", MB_OK | MB_ICONERROR);
    return (int)result;
}
