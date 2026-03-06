# HxCfgFileConverter COM Class Usage Guide

## Overview
The HxCfgFileConverterCOM class provides a COM interface for converting Hamilton configuration files from binary to ASCII format. The original binary file is never modified.

## COM Class Details
- **ProgID**: `HxCfgFilConverter.HxCfgFileConverterCOM`
- **Interface**: `IHxCfgFileConverter`
- **GUID**: `B2C3D4E5-6F70-8091-BCDE-F12345678901`

## Registration

### Build the Project
1. Build the project in Visual Studio (or using MSBuild)
2. The assembly will be automatically registered for COM during build (RegisterForComInterop is enabled)

### Manual Registration (if needed)
If you need to manually register the COM class, run as Administrator:

```cmd
regasm /codebase HxCfgFilConverter.dll
```

To unregister:
```cmd
regasm /u HxCfgFilConverter.dll
```

## Methods

### ConvertBinaryToAscii(binaryFilePath, asciiFilePath)
Converts a binary config file to ASCII format.

**Parameters:**
- `binaryFilePath` (string): Full path to the source binary file
- `asciiFilePath` (string): Full path where the ASCII file should be saved

**Returns:**
- `true` if conversion was successful
- `false` if conversion failed

### GetLastError()
Returns the last error message if the conversion failed.

**Returns:**
- Error message string, or empty string if no error

## Usage Examples

### VBScript Example
```vbscript
' Create the COM object
Set converter = CreateObject("HxCfgFilConverter.HxCfgFileConverterCOM")

' Convert binary file to ASCII
binaryPath = "C:\Hamilton\Config\method.cfg"
asciiPath = "C:\Output\method_ascii.cfg"

If converter.ConvertBinaryToAscii(binaryPath, asciiPath) Then
    WScript.Echo "Conversion successful!"
Else
    WScript.Echo "Conversion failed: " & converter.GetLastError()
End If

Set converter = Nothing
```

### VBA Example (Excel, Access, etc.)
```vb
Sub ConvertConfigFile()
    Dim converter As Object
    Dim binaryPath As String
    Dim asciiPath As String
    Dim success As Boolean
    
    ' Create the COM object
    Set converter = CreateObject("HxCfgFilConverter.HxCfgFileConverterCOM")
    
    ' Set file paths
    binaryPath = "C:\Hamilton\Config\method.cfg"
    asciiPath = "C:\Output\method_ascii.cfg"
    
    ' Perform conversion
    success = converter.ConvertBinaryToAscii(binaryPath, asciiPath)
    
    If success Then
        MsgBox "Conversion successful!", vbInformation
    Else
        MsgBox "Conversion failed: " & converter.GetLastError(), vbCritical
    End If
    
    Set converter = Nothing
End Sub
```

### C# Example
```csharp
using HxCfgFilConverter;

// Create instance of the COM class
var converter = new HxCfgFileConverterCOM();

// Convert binary file to ASCII
string binaryPath = @"C:\Hamilton\Config\method.cfg";
string asciiPath = @"C:\Output\method_ascii.cfg";

bool success = converter.ConvertBinaryToAscii(binaryPath, asciiPath);

if (success)
{
    Console.WriteLine("Conversion successful!");
}
else
{
    Console.WriteLine($"Conversion failed: {converter.GetLastError()}");
}
```

### PowerShell Example
```powershell
# Create the COM object
$converter = New-Object -ComObject HxCfgFilConverter.HxCfgFileConverterCOM

# Set file paths
$binaryPath = "C:\Hamilton\Config\method.cfg"
$asciiPath = "C:\Output\method_ascii.cfg"

# Perform conversion
$success = $converter.ConvertBinaryToAscii($binaryPath, $asciiPath)

if ($success) {
    Write-Host "Conversion successful!" -ForegroundColor Green
} else {
    Write-Host "Conversion failed: $($converter.GetLastError())" -ForegroundColor Red
}

# Release COM object
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($converter) | Out-Null
```

## Key Features
- ✅ Original binary file is never modified
- ✅ Converts binary to ASCII only (as requested)
- ✅ Automatically creates output directory if it doesn't exist
- ✅ Provides detailed error messages through GetLastError()
- ✅ Works with any COM-compatible language (VBScript, VBA, PowerShell, C#, C++, Python with comtypes, etc.)

## Error Handling
The COM class includes comprehensive error handling:
- Validates input parameters
- Checks if source file exists
- Creates output directory if needed
- Uses temporary files to protect the original
- Returns detailed error messages via GetLastError()

## Notes
- The assembly must be registered on the machine where it will be used
- Requires .NET Framework 4.8
- Uses 32-bit (x86) architecture
- This is a pure COM class library with no UI components
