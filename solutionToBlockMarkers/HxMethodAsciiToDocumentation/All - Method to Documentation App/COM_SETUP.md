# COM Direct Integration Setup

## What Changed

The application now uses **Hamilton COM objects directly from Python** instead of calling an external EXE. This is cleaner and doesn't require building a separate converter executable.

## How It Works

The application calls Hamilton's `HxCfgFile` COM object directly:
- **GUID**: `F4B19511-207B-11D1-8C7D-004095E12BC7`
- **Methods**: `LoadFile()` and `SerializeFile()`
- **Approach**: Direct Windows COM interop from Python

## Setup (Choose One)

### Option 1: Using pywin32 (Recommended)

**Easiest option - works with existing Hamilton installation**

```powershell
pip install pywin32
# Then restart your IDE/terminal for changes to take effect
```

#### After Installation:

If you encounter COM registration issues, run:

```powershell
# Navigate to where pywin32 is installed
python -m pip show pywin32  # Find location

# Then run (as Administrator):
python <pywin32_location>/Scripts/pywin32_postinstall.py -install
```

### Option 2: Using comtypes

**Alternative if pywin32 doesn't work**

```powershell
pip install comtypes
```

### Option 3: No pip - Just Hamilton COM

If you have Hamilton software installed and COM properly registered, the application may work without installing anything (though unlikely - we recommend Option 1).

## Verification

### Check if Hamilton COM is Available

Open Python and try:

```python
# With pywin32
import win32com.client
hx = win32com.client.GetObject("new:{F4B19511-207B-11D1-8C7D-004095E12BC7}")
print("COM object available!")
```

```python
# OR with comtypes
from comtypes.client import CreateObject
hx = CreateObject("{F4B19511-207B-11D1-8C7D-004095E12BC7}")
print("COM object available!")
```

### Run the Application

When you start the app, it will check if COM is available:

- ✅ If COM is found: All green, ready to use
- ⚠️ If COM is not found: Warning message with installation instructions

## Troubleshooting

### "Hamilton COM object is not available"

**Solution 1: Install pywin32**
```powershell
pip install pywin32
```

**Solution 2: Register COM after installation**
```powershell
# Run as Administrator
python -m pip install --upgrade pywin32
python <location>/Scripts/pywin32_postinstall.py -install
```

**Solution 3: Check Hamilton is installed**
- Verify you have Hamilton software installed on your system
- The COM object comes from Hamilton's libraries

### "ImportError: No module named 'comtypes'"

You installed the wrong package. Install one of:
```powershell
pip install pywin32      # Recommended
# OR
pip install comtypes     # Alternative
```

### Still "COM object not available" after installation?

1. **Restart IDE/Terminal** - Required after pip install
2. **Restart Python** - May need fresh Python interpreter
3. **Run as Administrator** - Some COM operations require admin
4. **Check Windows Registry**:
   ```powershell
   Get-Item "HKLM:\SOFTWARE\Classes\CLSID\{F4B19511-207B-11D1-8C7D-004095E12BC7}"
   ```
   If this errors, Hamilton COM isn't registered

### "Access Denied" when running application

Run VS Code or terminal as Administrator:
```
Right-click VS Code → Run as Administrator
```

## How to Tell It's Working

When you run the application:

1. GUI opens normally
2. **No warning message** about COM object
3. You can select a .med file
4. Conversion starts when you click "Generate"
5. First log message: "Conversion successful!"

## Comparison: Old vs New

### Before (External EXE)
- ❌ Had to build C# project separately
- ❌ Needed HxCfgFilConverter.exe in folder
- ❌ External process overhead
- ❌ More moving parts

### Now (Direct COM)
- ✅ Pure Python solution
- ✅ Just `pip install pywin32`
- ✅ Direct Hamilton library access
- ✅ Simpler architecture
- ✅ No build step needed

## What Converter.cs Did

For reference, here's what the old C# converter did:

```csharp
// Create COM object
hxCfgFile = Activator.CreateInstance(
    Marshal.GetTypeFromCLSID(
        new Guid("F4B19511-207B-11D1-8C7D-004095E12BC7")
    )
);

// Load binary file
status = hxCfgFile.LoadFile(filename);

// Convert to ASCII
hxCfgFile.SerializeFile(output_filename, status);
```

The Python code now does exactly this using COM interop libraries.

## If pywin32 Still Doesn't Work

You have two options:

### Option A: Minimal C# Console App (No COM wrapper needed)

Create a simple console app that takes two arguments:

```csharp
class Program
{
    static void Main(string[] args)
    {
        if (args.Length < 2)
        {
            Console.WriteLine("Usage: converter.exe <input.med> <output.txt>");
            return;
        }
        
        var converter = new Converter();
        converter.LoadFile(args[0]);
        converter.SerializeFile(args[1]);
    }
}
```

Then copy the exe to `converter_bin/` and the Python code will fall back to using it.

### Option B: Register COM Manually

```powershell
# If you have Hamilton installed
regsvcs HamiltonInterop.dll

# Or use Hamilton's own registration
cd "Program Files\Hamilton\Vector"
regsvr32 HxCfgFile.dll
```

## Summary

1. **Best**: `pip install pywin32` → Works immediately
2. **Alternative**: `pip install comtypes` → Also works
3. **Fallback**: Build C# console app → Most complex
4. **Manual**: Register Hamilton COM → Most manual

Try Option 1 first - it's what the code is optimized for.
