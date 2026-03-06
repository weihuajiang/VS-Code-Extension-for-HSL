# Setup Instructions for Direct COM Integration

## What You Need to Know

The application has been **refactored to use Hamilton COM objects directly** instead of an external EXE converter. This is simpler and faster to set up.

## ⚡ Quick Setup (TL;DR)

```powershell
pip install pywin32
# Restart your IDE/terminal
python MethodToDocumentation.py
```

That's it! 

## 📋 Detailed Setup

### Step 1: Install pywin32

Open PowerShell or Command Prompt and run:

```powershell
pip install pywin32
```

### Step 2: Restart Your IDE

This is important - Python needs to reload the environment:

- Close VS Code
- Close ANY open terminals
- Reopen VS Code
- Open a new terminal

**Why**: Environmental variables need to be refreshed after pip install.

### Step 3: Verify Installation (Optional)

Test that everything is working:

```powershell
python -c "import win32com.client; print('✓ Ready!')"
```

If you see "✓ Ready!", you're all set!

Alternatively, run:

```batch
check_setup.bat
```

### Step 4: Run the Application

```powershell
python MethodToDocumentation.py
```

Or double-click `run.bat` in Windows Explorer.

## 🤔 What About the Old Converter Files?

You'll see these files in the directory - **they're no longer used**:
- `setup_converter.bat` - ❌ Not needed
- `setup_converter.md` - ❌ Not needed
- `converter_bin/` - ❌ Not needed

Feel free to delete them or leave them. The new code doesn't use them.

## ⚠️ If Something Goes Wrong

### "ImportError: No module named 'win32com'"

```powershell
pip install pywin32
```

Then **restart your IDE/terminal**.

### "Hamilton COM object not available"

This usually means Hamilton software isn't installed. Check:

1. Is Hamilton Vector installed on your system?
2. Do you have .med files from Hamilton?

If you don't have Hamilton installed, you won't be able to convert .med files, but you can still use the application if they provide ASCII files instead.

### Still stuck?

See the full troubleshooting guide in [COM_SETUP.md](COM_SETUP.md)

## 🎯 Success Indicators

When you run the application, you should see:

✅ GUI opens with no warnings  
✅ You can select a .med file  
✅ Conversion completes when you click "Generate"  
✅ HTML files appear in output directory  

## Alternative Setup Methods

### Using requirements.txt

Instead of the pip command, you can run:

```powershell
pip install -r requirements.txt
```

This installs all dependencies listed in `requirements.txt`.

### If pywin32 Doesn't Work

The application has a fallback - it will also try `comtypes`:

```powershell
pip install comtypes
```

Both work similarly. Try pywin32 first (it's recommended).

## What Changed From Version 1.0?

| Aspect | v1.0 (Old) | v1.1 (New) |
|--------|-----------|-----------|
| Converter | External EXE | Direct COM |
| Setup | Build C# project | `pip install` |
| Complexity | High | Low |
| Dependencies | Many DLLs | Just pywin32 |
| Setup time | ~10 minutes | 1 minute |
| Documentation | Large | Simple |

## Next Steps

1. ✅ Install pywin32
2. ✅ Restart IDE
3. ✅ Run application
4. ✅ Select .med file
5. ✅ Generate HTML
6. ✅ View documentation
7. ✅ Share with team!

## Need Help?

- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **Full Documentation**: [README.md](README.md)
- **COM Details**: [COM_SETUP.md](COM_SETUP.md)
- **Implementation Notes**: [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md)
- **Verify Setup**: `check_setup.bat`

## One More Thing

Make sure you restart your IDE or terminal after installing pywin32 - it's a frequent cause of "module not found" errors.

---

**Ready?** Run: `python MethodToDocumentation.py` 🚀
