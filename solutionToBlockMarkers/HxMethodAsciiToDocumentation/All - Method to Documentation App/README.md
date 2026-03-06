# Method to Documentation - Unified Application

## Overview

This unified application combines three steps into one streamlined process:

1. **Convert .MED to ASCII**: Converts Hamilton .med method files to ASCII format
2. **Extract Submethods**: Parses the ASCII file to extract submethods and their parameters
3. **Generate HTML Documentation**: Creates professional HTML documentation for each submethod

## Features

- **User-Friendly GUI**: Simple interface to select input file and output directory
- **Automated Workflow**: All three steps are executed automatically
- **Professional HTML Output**: Clean, styled documentation with CSS
- **Progress Logging**: Real-time log display showing each step
- **Error Handling**: Comprehensive error messages and validation

## Requirements

- Python 3.8 or higher
- Windows operating system (for COM interop)
- Hamilton COM libraries (included with Hamilton software, or)
- **pywin32** package: `pip install pywin32`

## Setup Instructions

### Step 1: Install pywin32

This is the only requirement to enable .med file conversion:

```powershell
pip install pywin32
```

**Note**: You must restart your IDE or terminal after installing for the changes to take effect.

### Step 2: Verify Installation (Optional)

To verify pywin32 is working:

```powershell
python -c "import win32com.client; print('Ready to use!')"
```

If this shows "Ready to use!", you're all set.

For more information on troubleshooting COM setup, see [COM_SETUP.md](COM_SETUP.md).

## Usage

### Running the Application

1. **Start the Application**:
   ```powershell
   python MethodToDocumentation.py
   ```
   
   Or simply double-click `MethodToDocumentation.py` in Windows Explorer.

2. **Select Input File**:
   - Click "Browse..." next to ".MED File"
   - Select your Hamilton method file (.med)

3. **Select Output Directory**:
   - Click "Browse..." next to "Output Directory"
   - Choose where you want the HTML documentation saved

4. **Optional: Customize Author Name**:
   - Enter your name in the "Author Name" field
   - This will appear in the footer of all HTML files

5. **Generate Documentation**:
   - Click "Generate Documentation"
   - Watch the progress log for status updates
   - Wait for the success message

### Output

The application will create:

- **[MethodName].html** - One HTML file for each submethod
- **help.css** - Stylesheet for all HTML files
- Files are saved in your selected output directory

### Viewing Documentation

Open any of the generated HTML files in a web browser (Chrome, Firefox, Edge, etc.).

## How It Works

## How It Works

### Step 1: .MED to ASCII Conversion

The application uses Hamilton's COM object directly to convert the binary .med file:

**COM Object**: `HxCfgFile` (GUID: `F4B19511-207B-11D1-8C7D-004095E12BC7`)

**Process**:
1. Creates an instance of HxCfgFile COM object using pywin32
2. Calls `LoadFile()` to read the binary .med file
3. Calls `SerializeFile()` to convert to ASCII text format
4. Saves as temporary text file for parsing

### Step 2: Submethod Extraction

The parser reads the ASCII file and extracts:
- Submethod names
- Submethod descriptions
- Parameter names and descriptions

It looks for specific markers in the ASCII format:
- `-533725169`: Parameter section start
- `1-533725167`: Variable description
- `1-533725168`: Variable name
- `1-533725170`: Method description
- `1-533725161`: Method name

### Step 3: HTML Generation

For each submethod, the application generates:
- A formatted HTML page with header
- Description section
- Parameter table (if parameters exist)
- Footer with author name and year

All pages share a common CSS stylesheet for consistent styling.

## Troubleshooting

### "Hamilton COM object is not available" Error

**Problem**: The application cannot access the Hamilton COM libraries

**Solutions** (in order):
1. **Install pywin32**:
   ```powershell
   pip install pywin32
   ```

2. **Restart your IDE/Terminal** - Required after pip install

3. **Verify installation**:
   ```powershell
   python -c "import win32com.client; print('OK')"
   ```

4. **Run as Administrator** - Some COM operations require admin privileges

5. **Ensure Hamilton is Installed** - The COM object comes from Hamilton software

For detailed troubleshooting, see [COM_SETUP.md](COM_SETUP.md)

### "Failed to convert .MED file" Error

**Problem**: Conversion started but failed

**Solutions**:
1. Verify the .med file is valid and not corrupted
2. Try a different .med file to test
3. Ensure Hamilton software is correctly installed
4. Check that you have read/write permissions on the file
5. Check the error details in the application log

### "No submethods found" Warning

**Problem**: The parser didn't find any submethods in the ASCII file

**Possible Causes**:
1. The method file doesn't contain submethods
2. The ASCII format is different than expected
3. The conversion produced an empty or invalid file

**Solutions**:
1. Verify the .med file actually contains method definitions
2. Check if the method file is from a compatible Hamilton version
3. Try with a different .med file

### Python Errors

**Problem**: ImportError or other Python errors

**Solution**: Ensure Python 3.8+ and required packages:
```powershell
python --version
pip list | findstr pywin32
```

If pywin32 is not listed, run:
```powershell
pip install pywin32
```

## Advanced Usage

### Command Line Mode (Future Enhancement)

Currently, the application only supports GUI mode. Command line support could be added for batch processing.

### Customizing Output Format

To customize the HTML output:

1. Edit the `HTMLGenerator._create_css_file()` method to change styling
2. Edit the `HTMLGenerator.generate_html()` method to change HTML structure
3. Modify parameter table layout in the same method

### Batch Processing Multiple Files

To process multiple .med files:

1. Run the application for each file
2. Or modify the code to add a file list feature
3. Consider creating a PowerShell script to call the Python script multiple times

## Technical Details

### Dependencies

- **Python Standard Library**:
  - `tkinter` - GUI framework (built-in)
  - `csv`, `re`, `html`, `pathlib`, `tempfile`, `datetime`, `dataclasses` - Utilities

- **Third-Party** (one-time install):
  - `pywin32` - Windows COM interop (install with: `pip install pywin32`)

### Architecture

The application is organized into four main components:

1. **MedConverter**: Handles .med to ASCII conversion using COM interop (pywin32)
2. **SubmethodParser**: Parses ASCII format to extract structured data
3. **HTMLGenerator**: Creates HTML documentation from structured data
4. **MethodToDocumentationApp**: GUI application tying everything together

### File Format Details

The Hamilton ASCII format uses specific integer codes as markers:
- These codes are consistent across different Hamilton method files
- The parser is tuned to these specific codes
- If Hamilton changes their format, the parser may need updates

## License

This is an internal tool for documentation generation. Use in accordance with your organization's policies.

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review the log output in the application
3. Verify all setup steps were completed
4. Check that Hamilton software is properly installed

## Changelog

### Version 1.1 (February 2026)
- **Refactored**: Direct COM interop instead of external EXE
- **Simplified**: Only requires `pip install pywin32`
- **Improved**: No build step needed for converter
- **Better**: Cleaner architecture, fewer dependencies

### Version 1.0 (February 2026)
- Initial release
- Combined all three steps into unified application
- Added GUI interface
- Real-time progress logging
- Professional HTML output with CSS styling

## Credits

- Based on the three-step process developed for Hamilton method documentation
- Combines functionality from:
  - Step 1: HxBinaryToAsciiConversion (C#)
  - Step 2: Extract Submethods (Python)
  - Step 3: Create Documentation in HTML (Python)
