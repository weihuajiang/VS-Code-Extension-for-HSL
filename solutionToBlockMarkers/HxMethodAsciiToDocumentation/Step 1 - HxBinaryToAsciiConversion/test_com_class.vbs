' VBScript Test for HxCfgFileConverter COM Class

WScript.Echo "================================================"
WScript.Echo "HxCfgFileConverter COM Class Test (VBScript)"
WScript.Echo "================================================"
WScript.Echo ""

' Try to create the COM object
On Error Resume Next
Set converter = CreateObject("HxCfgFilConverter.HxCfgFileConverterCOM")

If Err.Number <> 0 Then
    WScript.Echo "ERROR: Failed to create COM object"
    WScript.Echo "Error: " & Err.Description
    WScript.Echo ""
    WScript.Echo "Make sure the COM class is registered."
    WScript.Echo "Run register_com.bat as Administrator."
    WScript.Quit 1
End If

WScript.Echo "✓ COM object created successfully!"
WScript.Echo ""

' Prompt for input file
binaryPath = InputBox("Enter the path to a binary config file:", "Binary File Path")

If binaryPath = "" Then
    WScript.Echo "No file specified. Exiting."
    WScript.Quit 0
End If

' Check if file exists
Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FileExists(binaryPath) Then
    WScript.Echo "ERROR: File not found: " & binaryPath
    WScript.Quit 1
End If

' Generate output path
Set inputFile = fso.GetFile(binaryPath)
outputPath = fso.GetParentFolderName(binaryPath) & "\" & _
             fso.GetBaseName(binaryPath) & "_ascii" & _
             fso.GetExtensionName(binaryPath)

If fso.GetExtensionName(binaryPath) <> "" Then
    outputPath = fso.GetParentFolderName(binaryPath) & "\" & _
                 fso.GetBaseName(binaryPath) & "_ascii." & _
                 fso.GetExtensionName(binaryPath)
End If

WScript.Echo "Input file:  " & binaryPath
WScript.Echo "Output file: " & outputPath
WScript.Echo ""

' Perform conversion
WScript.Echo "Converting binary to ASCII..."
success = converter.ConvertBinaryToAscii(binaryPath, outputPath)

If success Then
    WScript.Echo "✓ Conversion successful!"
    WScript.Echo ""
    WScript.Echo "Output file created: " & outputPath
    
    If fso.FileExists(outputPath) Then
        WScript.Echo "  Input file size:  " & inputFile.Size & " bytes"
        Set outputFile = fso.GetFile(outputPath)
        WScript.Echo "  Output file size: " & outputFile.Size & " bytes"
    End If
Else
    errorMsg = converter.GetLastError()
    WScript.Echo "✗ Conversion failed!"
    WScript.Echo "  Error: " & errorMsg
End If

WScript.Echo ""
WScript.Echo "================================================"
WScript.Echo "Test Complete"
WScript.Echo "================================================"

Set converter = Nothing
Set fso = Nothing
