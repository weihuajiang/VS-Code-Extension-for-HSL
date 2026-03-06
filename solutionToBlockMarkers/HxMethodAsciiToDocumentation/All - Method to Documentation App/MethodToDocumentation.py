"""
Method to Documentation - Unified Application
===============================================
This application combines three steps:
1. Convert .med file to ASCII format
2. Extract submethods and parameters from ASCII
3. Generate HTML documentation for each submethod

Author: Unified Automation Tool
Date: February 2026
"""

import os
import sys
import csv
import re
import html
import tempfile
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from dataclasses import dataclass
from typing import List, Dict


# ========================================
# Step 1: .MED to ASCII Conversion
# ========================================
class MedConverter:
    """Handles conversion of .med files to ASCII format using HxCfgFilConverter.exe."""
    
    def __init__(self):
        """Initialize the converter by checking for converter availability."""
        self.converter_path = self._find_converter()
        self.com_available = self.converter_path is not None
    
    @staticmethod
    def _find_converter() -> Path:
        """
        Find the HxCfgFilConverter.exe in the application directory.
        
        Returns:
            Path to converter executable, or None if not found
        """
        # Look for converter in the app directory
        script_dir = Path(__file__).parent
        converter_path = script_dir / "converter_bin" / "HxCfgFilConverter.exe"
        
        if converter_path.exists():
            return converter_path
        return None
    
    def convert_to_ascii(self, med_file_path: str, output_txt_path: str) -> bool:
        """
        Convert a .med file to ASCII format using HxCfgFilConverter.exe.
        
        Args:
            med_file_path: Path to the input .med file
            output_txt_path: Path for the output ASCII text file
            
        Returns:
            True if conversion succeeded, False otherwise
        """
        if not self.com_available:
            raise RuntimeError(
                "HxCfgFilConverter.exe not found.\n\n"
                "Looking for: converter_bin\\HxCfgFilConverter.exe\n\n"
                "Please ensure the converter is in the correct location."
            )
        
        try:
            # Convert paths to absolute
            med_file_path = str(Path(med_file_path).resolve())
            output_txt_path = str(Path(output_txt_path).resolve())
            
            # The converter modifies files in-place, so:
            # 1. Copy input to output location
            # 2. Run converter on output file
            shutil.copy2(med_file_path, output_txt_path)
            
            # Run the converter (use /t flag to convert TO text/ASCII)
            result = subprocess.run(
                [str(self.converter_path), "/t", output_txt_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check if conversion succeeded
            if result.returncode == 0:
                # Verify output was created and has content
                if Path(output_txt_path).exists() and Path(output_txt_path).stat().st_size > 0:
                    return True
                else:
                    print(f"Error: Output file not created or is empty")
                    return False
            else:
                print(f"Converter failed with return code: {result.returncode}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("Error: Conversion timed out after 30 seconds")
            return False
        except Exception as e:
            print(f"Conversion error: {e}")
            import traceback
            traceback.print_exc()
            return False


# ========================================
# Step 2: Submethod Extraction
# ========================================
class SubmethodParser:
    """Parses ASCII method files to extract submethods and their parameters."""
    
    @staticmethod
    def clean_description(desc: str) -> str:
        """Clean up description text by removing special characters and formatting."""
        if not desc:
            return ""
        # Remove \r\n and replace with spaces
        desc = desc.replace('\\r\\n', ' ')
        # Remove special hex characters like \0xb5 and \0x93
        desc = re.sub(r'\\0x[0-9a-fA-F]{2}', '', desc)
        # Clean up multiple spaces
        desc = re.sub(r'\s+', ' ', desc)
        return desc.strip()
    
    @staticmethod
    def parse_submethods(file_path: str) -> List[Dict]:
        """
        Parse the ASCII file and extract all submethods.
        
        Args:
            file_path: Path to the ASCII text file
            
        Returns:
            List of submethod dictionaries with name, description, and variables
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip().strip(',').strip('"') for line in f]
        
        submethods = []
        i = 0
        
        while i < len(lines):
            # Look for parameter section marker (-533725169)
            # This marks the start of a method's parameter list
            if lines[i] == '(-533725169':
                method_data = {
                    'name': '',
                    'description': '',
                    'variables': []
                }
                
                # Parse all variables in this parameters section
                i += 1
                
                while i < len(lines):
                    line = lines[i]
                    
                    # Track when we enter/exit parameter blocks
                    if re.match(r'^\(\d+$', line):
                        # Start of a parameter block like "(0", "(1", "(2"
                        var_description = ''
                        var_name = ''
                        
                        # Scan through this parameter block
                        j = i + 1
                        while j < len(lines):
                            if lines[j] == ')':
                                # End of this parameter block
                                break
                            elif lines[j] == '1-533725167':
                                # Next line contains variable description
                                if j + 1 < len(lines):
                                    var_description = lines[j + 1]
                                    j += 1
                            elif lines[j] == '1-533725168':
                                # Next line contains variable name
                                if j + 1 < len(lines):
                                    var_name = lines[j + 1]
                                    j += 1
                            j += 1
                        
                        # Add variable if we found a name
                        if var_name:
                            method_data['variables'].append({
                                'name': var_name,
                                'description': var_description
                            })
                        
                        # Move past this parameter block
                        i = j
                    
                    elif line == ')':
                        # Check if this closes the entire parameters section
                        # by looking ahead for description and method name markers
                        if i + 1 < len(lines) and lines[i + 1] == '1-533725170':
                            # This closes the parameters section
                            # Now get description and method name
                            i += 1  # Move to 1-533725170
                            if i + 1 < len(lines):
                                method_data['description'] = SubmethodParser.clean_description(lines[i + 1])
                                i += 1  # Move to description text
                            
                            # Look for method name ahead
                            while i < len(lines):
                                if lines[i] == '1-533725161':
                                    if i + 1 < len(lines):
                                        method_data['name'] = lines[i + 1]
                                    break
                                i += 1
                            
                            # Add method to list
                            if method_data['name']:
                                submethods.append(method_data)
                            break
                    
                    i += 1
            else:
                i += 1
        
        return submethods


# ========================================
# Step 3: HTML Documentation Generation
# ========================================
@dataclass
class ParameterDoc:
    """Documentation for a single parameter."""
    name: str
    description: str


@dataclass
class SubmethodDoc:
    """Documentation for a single submethod."""
    name: str
    description: str
    parameters: List[ParameterDoc]


class HTMLGenerator:
    """Generates HTML documentation for submethods."""
    
    def __init__(self, output_directory: str, author_name: str = "Zachary Milot 2026"):
        """
        Initialize the HTML generator.
        
        Args:
            output_directory: Directory where HTML files will be saved
            author_name: Name to display in footer
        """
        self.output_dir = Path(output_directory)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.author_name = author_name
        self.year = datetime.now().year
        
        # Create CSS file
        self._create_css_file()
    
    def _create_css_file(self):
        """Create the help.css file for styling HTML documentation."""
        css_content = """/* Documentation Stylesheet */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    background-color: #f5f5f5;
    color: #333;
    line-height: 1.6;
}

.header {
    background-color: #2c3e50;
    color: #ecf0f1;
    padding: 20px 30px;
    font-size: 28px;
    font-weight: bold;
    border-bottom: 4px solid #3498db;
}

.main {
    max-width: 1200px;
    margin: 30px auto;
    padding: 30px;
    background-color: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    border-radius: 8px;
}

h2 {
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 8px;
    margin-top: 30px;
    margin-bottom: 15px;
    font-size: 22px;
}

h2:first-of-type {
    margin-top: 0;
}

p {
    margin: 10px 0;
    color: #555;
}

ul {
    margin: 10px 0;
    padding-left: 25px;
}

li {
    margin: 5px 0;
    color: #555;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 20px 0;
    background-color: white;
}

thead {
    background-color: #3498db;
    color: white;
}

th {
    padding: 12px 10px;
    text-align: left;
    font-weight: 600;
    border: 1px solid #2980b9;
}

td {
    padding: 10px;
    border: 1px solid #ddd;
    vertical-align: top;
}

tbody tr:nth-child(even) {
    background-color: #f9f9f9;
}

tbody tr:hover {
    background-color: #e8f4f8;
}

.footer {
    background-color: #34495e;
    color: #ecf0f1;
    text-align: center;
    padding: 15px;
    margin-top: 40px;
    font-size: 14px;
}

.footer p {
    margin: 0;
    color: #ecf0f1;
}

code {
    background-color: #f4f4f4;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
    font-size: 90%;
}
"""
        css_path = self.output_dir / "help.css"
        css_path.write_text(css_content, encoding='utf-8')
    
    def _safe_filename(self, name: str) -> str:
        """Convert a method name to a safe filename."""
        return re.sub(r'[<>:"/\\|?*\s]+', '_', name).strip('_') or 'function'
    
    def _render_description_html(self, description: str) -> str:
        """
        Convert description text to HTML.
        
        Args:
            description: Raw description text
            
        Returns:
            HTML formatted description
        """
        if not description or not description.strip():
            return "<p>No description available.</p>"
        
        # Split into lines and process
        lines = description.split('\n')
        paragraphs = []
        current_para = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
            else:
                current_para.append(stripped)
        
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        # Convert to HTML
        if not paragraphs:
            return "<p>No description available.</p>"
        
        html_parts = []
        for para in paragraphs:
            html_parts.append(f"<p>{html.escape(para)}</p>")
        
        return '\n'.join(html_parts)
    
    def generate_html(self, submethod_doc: SubmethodDoc) -> str:
        """
        Generate HTML content for a submethod.
        
        Args:
            submethod_doc: SubmethodDoc object
            
        Returns:
            Complete HTML content as string
        """
        title = html.escape(submethod_doc.name)
        header = html.escape(submethod_doc.name)
        desc_html = self._render_description_html(submethod_doc.description)
        
        # Build parameter table rows
        if submethod_doc.parameters:
            rows_html = "\n".join(
                "<tr>"
                f"<td style=\"width: 30%;\">{html.escape(p.name)}</td>"
                f"<td style=\"width: 70%;\">{html.escape(p.description or 'No description')}</td>"
                "</tr>"
                for p in submethod_doc.parameters
            )
            
            param_table = f"""<h2>Parameters</h2>
<table class="table table-bordered" style="width: 100%;">
<thead>
<tr>
<th style="width: 30%;">Parameter Name</th>
<th style="width: 70%;">Description</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>"""
        else:
            param_table = "<h2>Parameters</h2>\n<p>This submethod has no parameters.</p>"
        
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta charset="utf-8">
    <link rel="stylesheet" type="text/css" href="help.css">
</head>
<body>
    <div class="header">{header}</div>
    <div class="main">
        <h2>Description</h2>
        {desc_html}
        {param_table}
    </div>
    <div class="footer">
        <p>{html.escape(self.author_name)} {self.year}</p>
    </div>
</body>
</html>"""
    
    def write_html_file(self, submethod_doc: SubmethodDoc) -> str:
        """
        Generate and write HTML file for a submethod.
        
        Args:
            submethod_doc: SubmethodDoc object
            
        Returns:
            Path to the created file
        """
        html_content = self.generate_html(submethod_doc)
        filename = f"{self._safe_filename(submethod_doc.name)}.html"
        file_path = self.output_dir / filename
        file_path.write_text(html_content, encoding='utf-8')
        return str(file_path)
    
    def generate_all_html(self, submethods: List[Dict]) -> List[str]:
        """
        Generate HTML files for all submethods.
        
        Args:
            submethods: List of submethod dictionaries from parser
            
        Returns:
            List of file paths created
        """
        created_files = []
        
        for method_data in submethods:
            # Convert to SubmethodDoc
            params = [
                ParameterDoc(
                    name=var['name'],
                    description=SubmethodParser.clean_description(var['description'])
                )
                for var in method_data['variables']
            ]
            
            doc = SubmethodDoc(
                name=method_data['name'],
                description=method_data['description'],
                parameters=params
            )
            
            file_path = self.write_html_file(doc)
            created_files.append(file_path)
        
        return created_files


# ========================================
# Main Application GUI
# ========================================
class MethodToDocumentationApp(tk.Tk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.title("Method to Documentation Generator")
        self.geometry("900x600")
        self.minsize(800, 500)
        
        # Initialize converter
        self.converter = MedConverter()
        
        # Variables
        self.med_file_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.author_name_var = tk.StringVar(value="Auto-Generated Documentation")
        self.status_var = tk.StringVar(value="Ready. Please select a .med file and output directory.")
        
        self._build_ui()
        
        # Check if converter is available
        if not self.converter.com_available:
            self.log_message("WARNING: HxCfgFilConverter.exe not found!", "warning")
            self.log_message("Looking for: converter_bin\\HxCfgFilConverter.exe", "warning")
            self.log_message("", "warning")
            self.log_message("Conversion from .med to ASCII will not work.", "warning")
    
    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill="both", expand=True)
        
        # ===== Input File Selection =====
        input_frame = ttk.LabelFrame(main_frame, text="Input Settings", padding=10)
        input_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(input_frame, text=".MED File:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(input_frame, textvariable=self.med_file_var, width=60).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(input_frame, text="Browse...", command=self.browse_med_file).grid(row=0, column=2, padx=5)
        
        input_frame.columnconfigure(1, weight=1)
        
        # ===== Output Settings =====
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding=10)
        output_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(output_frame, text="Output Directory:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=60).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(output_frame, text="Browse...", command=self.browse_output_dir).grid(row=0, column=2, padx=5)
        
        ttk.Label(output_frame, text="Author Name:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(output_frame, textvariable=self.author_name_var, width=60).grid(row=1, column=1, sticky="ew", padx=5)
        
        output_frame.columnconfigure(1, weight=1)
        
        # ===== Log Display =====
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(log_frame)
        text_frame.pack(fill="both", expand=True)
        
        self.log_text = tk.Text(text_frame, wrap="word", height=15, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # Configure text tags for colored output
        self.log_text.tag_configure("info", foreground="black")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("error", foreground="red")
        
        # ===== Action Buttons =====
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        ttk.Label(button_frame, textvariable=self.status_var).pack(side="left", anchor="w")
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Generate Documentation", command=self.generate_documentation, 
                  style="Accent.TButton").pack(side="right")
    
    def browse_med_file(self):
        """Open file browser for .med file selection."""
        file_path = filedialog.askopenfilename(
            title="Select .MED File",
            filetypes=[("Method Files", "*.med"), ("All Files", "*.*")]
        )
        if file_path:
            self.med_file_var.set(file_path)
            self.log_message(f"Selected input file: {file_path}", "info")
    
    def browse_output_dir(self):
        """Open directory browser for output directory selection."""
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        if dir_path:
            self.output_dir_var.set(dir_path)
            self.log_message(f"Selected output directory: {dir_path}", "info")
    
    def log_message(self, message: str, level: str = "info"):
        """
        Add a message to the log display.
        
        Args:
            message: Message to log
            level: Log level (info, success, warning, error)
        """
        self.log_text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n", level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.update_idletasks()
    
    def clear_log(self):
        """Clear the log display."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
    
    def generate_documentation(self):
        """Main workflow to generate documentation."""
        # Validate inputs
        med_file = self.med_file_var.get().strip()
        output_dir = self.output_dir_var.get().strip()
        author_name = self.author_name_var.get().strip()
        
        if not med_file:
            messagebox.showerror("Missing Input", "Please select a .MED file.")
            return
        
        if not output_dir:
            messagebox.showerror("Missing Output", "Please select an output directory.")
            return
        
        if not Path(med_file).exists():
            messagebox.showerror("File Not Found", f"The file does not exist:\n{med_file}")
            return
        
        # Disable button during processing
        self.status_var.set("Processing...")
        self.update_idletasks()
        
        try:
            # Step 1: Convert .med to ASCII
            self.log_message("=" * 60, "info")
            self.log_message("STEP 1: Converting .MED to ASCII", "info")
            self.log_message("=" * 60, "info")
            
            # Create temporary file for ASCII output
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
                ascii_file_path = tmp_file.name
            
            self.log_message(f"Input: {med_file}", "info")
            self.log_message(f"Temporary ASCII file: {ascii_file_path}", "info")
            
            if not self.converter.convert_to_ascii(med_file, ascii_file_path):
                raise Exception("Failed to convert .MED file to ASCII. Check converter setup.")
            
            self.log_message("✓ Conversion successful!", "success")
            
            # Step 2: Parse submethods
            self.log_message("", "info")
            self.log_message("=" * 60, "info")
            self.log_message("STEP 2: Extracting Submethods", "info")
            self.log_message("=" * 60, "info")
            
            parser = SubmethodParser()
            submethods = parser.parse_submethods(ascii_file_path)
            
            self.log_message(f"✓ Found {len(submethods)} submethod(s)", "success")
            
            if not submethods:
                self.log_message("Warning: No submethods found in file. Nothing to document.", "warning")
                messagebox.showwarning("No Submethods", "No submethods were found in the file.")
                return
            
            # Log found submethods
            for i, method in enumerate(submethods[:10], 1):  # Show first 10
                param_count = len(method['variables'])
                self.log_message(f"  {i}. {method['name']} ({param_count} parameter(s))", "info")
            
            if len(submethods) > 10:
                self.log_message(f"  ... and {len(submethods) - 10} more", "info")
            
            # Step 3: Generate HTML documentation
            self.log_message("", "info")
            self.log_message("=" * 60, "info")
            self.log_message("STEP 3: Generating HTML Documentation", "info")
            self.log_message("=" * 60, "info")
            
            generator = HTMLGenerator(output_dir, author_name)
            self.log_message(f"Output directory: {output_dir}", "info")
            
            created_files = generator.generate_all_html(submethods)
            
            self.log_message(f"✓ Created {len(created_files)} HTML file(s)", "success")
            self.log_message(f"✓ CSS stylesheet created: help.css", "success")
            
            # Clean up temporary file
            try:
                Path(ascii_file_path).unlink()
            except:
                pass
            
            # Success message
            self.log_message("", "info")
            self.log_message("=" * 60, "success")
            self.log_message("✓ DOCUMENTATION GENERATION COMPLETE!", "success")
            self.log_message("=" * 60, "success")
            
            self.status_var.set(f"Success! Created {len(created_files)} HTML files.")
            
            messagebox.showinfo(
                "Success",
                f"Documentation generated successfully!\n\n"
                f"Created {len(created_files)} HTML files in:\n{output_dir}\n\n"
                f"Open any HTML file in a web browser to view the documentation."
            )
            
        except FileNotFoundError as e:
            self.log_message(f"✗ Error: {str(e)}", "error")
            self.status_var.set("Failed - COM object not available")
            messagebox.showerror("COM Object Not Found", str(e))
            
        except Exception as e:
            self.log_message(f"✗ Error: {str(e)}", "error")
            self.status_var.set("Failed - See log for details")
            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")
        
        finally:
            # Re-enable button
            self.update_idletasks()


# ========================================
# Application Entry Point
# ========================================
def main():
    """Main entry point for the application."""
    app = MethodToDocumentationApp()
    app.mainloop()


if __name__ == "__main__":
    main()
