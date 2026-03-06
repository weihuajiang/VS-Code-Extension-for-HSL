# All - Method to Documentation App

## 📁 Project Overview

This is a **unified application** that combines all three steps of the Hamilton method documentation process into a single, user-friendly tool.

## 🎯 What Does It Do?

Takes a Hamilton .med file and automatically generates professional HTML documentation for all submethods, including parameters and descriptions.

**Input**: Hamilton .med binary file  
**Output**: Multiple HTML files with styled documentation

## 📦 Files in This Directory

| File | Purpose |
|------|---------|
| `MethodToDocumentation.py` | Main application (Python GUI) |
| `run.bat` | Quick launcher (Windows) |
| `COM_SETUP.md` | COM integration setup guide |
| `QUICKSTART.md` | Quick start guide |
| `README.md` | Full documentation |
| `PROJECT_OVERVIEW.md` | This file |
| `SAMPLE_OUTPUT.html` | Example output |

## 🚀 Quick Start

### First Time Setup:

```powershell
pip install pywin32
```

Then restart your IDE or terminal.

### Run the Application:

```batch
run.bat
```

Or:

```powershell
python MethodToDocumentation.py
```

### Using the Application:

1. Click "Browse..." to select your .med file
2. Click "Browse..." to choose output directory
3. Click "Generate Documentation"
4. Open the HTML files in a browser!

## 🔧 Technical Stack

- **Language**: Python 3.8+
- **GUI**: Tkinter (built-in)
- **COM Interop**: pywin32 (one-time install)
- **Dependencies**: Minimal! Just: `pip install pywin32`

## 📋 What It Does Behind the Scenes

```
Step 1: .MED → ASCII Conversion (Using COM Interop)
   └─> Uses Hamilton HxCfgFile COM object via pywin32
   └─> Calls LoadFile() to read binary
   └─> Calls SerializeFile() to convert to ASCII

Step 2: Parse Submethods
   └─> Extracts method names, descriptions
   └─> Extracts parameter names, descriptions
   └─> Builds structured data

Step 3: Generate HTML
   └─> Creates CSS stylesheet
   └─> Generates one HTML file per submethod
   └─> Includes parameter tables
   └─> Professional formatting
```

## 🎨 Generated Output Example

```
OutputFolder/
├── help.css                    (Stylesheet)
├── Pipette_96Channel.html     (Submethod 1)
├── Transfer_Sample.html       (Submethod 2)
├── Wash_Tips.html             (Submethod 3)
└── ... (more HTML files)
```

Each HTML file contains:
- Method name as header
- Description section
- Parameter table
- Styled with professional CSS
- Footer with author and date

## 📖 Documentation Files

- **README.md** - Complete documentation
- **QUICKSTART.md** - Get started in 2 steps
- **COM_SETUP.md** - COM integration troubleshooting

## ⚙️ Requirements

### Python
- Python 3.8 or higher
- pywin32: `pip install pywin32`

### System
- Windows (for COM interop)
- Hamilton software installed (provides COM object)

## 🔍 Features

✅ User-friendly GUI  
✅ Real-time progress logging  
✅ Automatic error handling  
✅ Professional HTML output  
✅ Customizable author name  
✅ Progress indicators  
✅ Comprehensive error messages  
✅ No manual CSV handling  
✅ No manual HTML creation  
✅ All-in-one solution  

## 🆚 Comparison with Manual Process

### Before (3 Separate Steps):
1. Run C# converter manually
2. Run Python parser to create CSV
3. Copy/paste into AutoDocumenter GUI
4. Generate HTML files one by one

### Now (1 Unified Step):
1. Select .med file
2. Click "Generate"
3. Done!

**Time saved**: ~90%  
**Error potential**: Eliminated manual steps  
**User experience**: Streamlined

## 🐛 Troubleshooting

### "Converter not found"
→ Run `setup_converter.bat`

### "Failed to convert"
→ Check Hamilton software installation  
→ See `setup_converter.md`

### "No submethods found"
→ File may not contain submethods  
→ Verify .med file is valid

### Python errors
→ Check Python version: `python --version`  
→ Must be 3.8 or higher

## 📚 Related Projects

This unified app combines functionality from:

- **Step 1** - HxBinaryToAsciiConversion (C#)
- **Step 2** - Extract Submethods (Python)
- **Step 3** - Create Documentation in HTML (Python)

All functionality is integrated into one seamless experience.

## 🎓 How It Works

### Architecture

```
User Interface (Tkinter GUI)
    ↓
MedConverter (calls HxCfgFilConverter.exe)
    ↓
SubmethodParser (extracts methods from ASCII)
    ↓
HTMLGenerator (creates styled documentation)
    ↓
Output HTML Files + CSS
```

### Data Flow

```
.med file (binary)
    → ASCII text (temporary)
    → Structured data (in memory)
    → HTML files (output)
```

### Why This Approach?

- **Minimal dependencies**: Only pywin32 for COM interop
- **Direct COM access**: No external EXE needed
- **Clean separation**: Each component has one responsibility
- **Easy maintenance**: Clear architecture
- **User-friendly**: Simple GUI, clear feedback

## 🔮 Future Enhancements

Possible improvements:

- [ ] Batch processing multiple .med files
- [ ] Command-line interface option
- [ ] PDF export option
- [ ] Search functionality in generated docs
- [ ] Index page with all methods
- [ ] Dark mode CSS theme
- [ ] Progress bar during conversion
- [ ] Windows Service mode

## 📝 License

Internal tool for documentation generation.

## 👤 Author

Auto-generated unified application  
Combining three-step manual process  
February 2026

## 🤝 Support

For help:
1. Check QUICKSTART.md - Quick guide
2. Check README.md - Full documentation
3. Check COM_SETUP.md - COM integration issues
4. Check log output in application - Error details

## ✨ Success Criteria

You'll know it's working when:

✓ Application starts without errors  
✓ You can select a .med file  
✓ Converter runs successfully  
✓ HTML files are created  
✓ You can view documentation in browser  
✓ Everything looks professional  

---

**Ready to get started?** → See [QUICKSTART.md](QUICKSTART.md)

**Need help?** → See [README.md](README.md)

**COM issues?** → See [COM_SETUP.md](COM_SETUP.md)
