# Converter Setup Guide

## What is the Converter?

The converter (`HxCfgFilConverter.exe`) is a C# application that uses Hamilton's COM libraries to convert binary .med files to ASCII text format. This conversion is necessary because the binary format cannot be directly parsed.

## Why Do We Need It?

Hamilton method files (.med) are stored in a proprietary binary format. The only way to read the contents is through Hamilton's own libraries (HxCfgFile COM component). The converter wraps this functionality to make it accessible to our Python application.

## Setup Methods

### Method 1: Build from Source (Recommended)

1. **Open Visual Studio**
   - Launch Visual Studio 2019 or later
   - Open the solution file:
     ```
     ..\Step 1 - HxBinaryToAsciiConversion\config file extract.sln
     ```

2. **Build the Project**
   - Select Build > Build Solution (or press F6)
   - Choose either Debug or Release configuration
   - Wait for build to complete

3. **Copy Built Files**
   - Navigate to the build output folder:
     ```
     ..\Step 1 - HxBinaryToAsciiConversion\bin\Debug\net48\
     ```
     (or `Release\net48\` if you built in Release mode)
   
   - Copy ALL files from this folder to:
     ```
     .\converter_bin\
     ```

4. **Verify Installation**
   - Check that `converter_bin\HxCfgFilConverter.exe` exists
   - Verify all DLL files are present

### Method 2: Use Existing Build

If you've already built the converter for Step 1:

1. **Copy Files with PowerShell**:
   ```powershell
   # From the "All - Method to Documentation App" directory
   Copy-Item "..\Step 1 - HxBinaryToAsciiConversion\bin\Debug\net48\*" `
       ".\converter_bin\" -Recurse -Force
   ```

2. **Or use the provided batch script**:
   ```batch
   setup_converter.bat
   ```

### Method 3: Manual Copy

1. Navigate to:
   ```
   ..\Step 1 - HxBinaryToAsciiConversion\bin\Debug\net48\
   ```

2. Copy these files to `converter_bin\`:
   - HxCfgFilConverter.exe
   - HxCfgFilConverter.dll (if present)
   - Hamilton.Interop.HxCfgFil.dll (if present)
   - Hamilton.Interop.HxReg.dll (if present)
   - Any other DLL files
   - HxCfgFilConverter.exe.config

## COM Registration

The converter uses COM interop, which requires Hamilton's COM libraries to be available on your system.

### Prerequisites

- Hamilton Vector software installed, OR
- Hamilton libraries registered in Windows Registry

### Registering COM Components

If you get COM-related errors:

1. **Check if Hamilton is Installed**
   - Look for Hamilton Vector in Program Files
   - Verify Hamilton libraries exist

2. **Register the Libraries** (if needed)
   
   Navigate to Step 1 folder and run as Administrator:
   ```powershell
   cd "..\Step 1 - HxBinaryToAsciiConversion"
   .\register_com.bat
   ```

3. **Required GUIDs**
   
   The converter looks for:
   - **HxCfgFile**: `F4B19511-207B-11D1-8C7D-004095E12BC7`
   
   These must be registered in the Windows Registry.

## Testing the Converter

### Command Line Test

Test the converter manually before using it in the application:

```powershell
cd converter_bin
.\HxCfgFilConverter.exe "C:\path\to\your\method.med" "output.txt"
```

Expected result:
- Exit code: 0 (success)
- Output file created: `output.txt`
- No error messages

### Verify Output

1. Open `output.txt` in a text editor
2. You should see ASCII text with numerical markers
3. Look for patterns like:
   ```
   (-533725169
   (0
   1-533725168
   "VariableName"
   ```

4. If the file is empty or contains binary data, the conversion failed

## Troubleshooting

### Error: "Could not load file or assembly"

**Problem**: Missing DLL dependencies

**Solution**:
1. Ensure ALL files from the build output were copied
2. Copy the entire bin\Debug\net48\ folder contents
3. Don't cherry-pick individual files

### Error: "Retrieving the COM class factory" failed

**Problem**: Hamilton COM components not registered

**Solutions**:
1. Install Hamilton Vector software
2. Register COM components (see above)
3. Run the converter as Administrator
4. Check Windows Registry for the GUID

### Error: "Could not create instance of HxCfgFile"

**Problem**: COM object cannot be instantiated

**Solutions**:
1. Verify Hamilton software is installed
2. Check if CLSID exists in Registry:
   ```powershell
   Get-Item "HKLM:\SOFTWARE\Classes\CLSID\{F4B19511-207B-11D1-8C7D-004095E12BC7}"
   ```
3. Re-register COM components
4. Restart computer after registration

### Converter Runs but Produces Empty File

**Problem**: Conversion process failed silently

**Solutions**:
1. Check .med file is valid (not corrupted)
2. Verify you have read/write permissions
3. Try a different .med file
4. Check Hamilton software version compatibility

### Application Can't Find Converter

**Problem**: Path issues

**Solutions**:
1. Verify file is at: `converter_bin\HxCfgFilConverter.exe`
2. Check file permissions (must be executable)
3. Use absolute path in application if needed
4. Don't rename the executable

## Alternative: Direct COM Access from Python

If you want to avoid the separate executable, you could modify the Python code to use COM directly via `comtypes` or `pywin32`:

```python
# Install: pip install pywin32
import win32com.client

# Create HxCfgFile COM object
hxCfgFile = win32com.client.Dispatch("{F4B19511-207B-11D1-8C7D-004095E12BC7}")

# Load and serialize
status = hxCfgFile.LoadFile("input.med")
hxCfgFile.SerializeFile("output.txt", status)
```

This approach still requires COM registration but eliminates the need for the separate executable.

## File Locations Reference

```
Project Root/
│
├── Step 1 - HxBinaryToAsciiConversion/
│   ├── bin/
│   │   └── Debug/
│   │       └── net48/                    ← Source files here
│   │           ├── HxCfgFilConverter.exe
│   │           └── *.dll
│   └── register_com.bat
│
└── All - Method to Documentation App/
    ├── MethodToDocumentation.py
    ├── converter_bin/                     ← Destination here
    │   ├── HxCfgFilConverter.exe
    │   └── *.dll
    └── README.md
```

## Summary Checklist

- [ ] Visual Studio installed
- [ ] Solution file opened and built
- [ ] All files from bin\Debug\net48\ copied to converter_bin\
- [ ] HxCfgFilConverter.exe exists in converter_bin\
- [ ] Hamilton software installed OR COM components registered
- [ ] Converter tested manually with a .med file
- [ ] Output verified (ASCII text, not binary)
- [ ] Python application can find converter
- [ ] Ready to generate documentation!

## Need Help?

1. Check error messages in the application log
2. Test converter manually from command line
3. Verify all prerequisites are met
4. Ensure Hamilton software is properly installed
5. Check Windows Event Viewer for COM errors
