# PowerShell Test Script for HxCfgFileConverter COM Class
# This script tests the COM class functionality

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "HxCfgFileConverter COM Class Test" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Try to create the COM object
try {
    Write-Host "Creating COM object..." -ForegroundColor Yellow
    $converter = New-Object -ComObject HxCfgFilConverter.HxCfgFileConverterCOM
    Write-Host "✓ COM object created successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Prompt for input file
    Write-Host "Please provide the path to a binary config file to test:" -ForegroundColor Yellow
    $binaryPath = Read-Host "Binary file path"
    
    if (-not (Test-Path $binaryPath)) {
        Write-Host "✗ Error: File not found: $binaryPath" -ForegroundColor Red
        exit 1
    }
    
    # Generate output path
    $binaryFile = Get-Item $binaryPath
    $outputPath = Join-Path $binaryFile.DirectoryName ($binaryFile.BaseName + "_ascii" + $binaryFile.Extension)
    
    Write-Host ""
    Write-Host "Input file:  $binaryPath" -ForegroundColor Cyan
    Write-Host "Output file: $outputPath" -ForegroundColor Cyan
    Write-Host ""
    
    # Perform conversion
    Write-Host "Converting binary to ASCII..." -ForegroundColor Yellow
    $success = $converter.ConvertBinaryToAscii($binaryPath, $outputPath)
    
    if ($success) {
        Write-Host "✓ Conversion successful!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Output file created: $outputPath" -ForegroundColor Green
        
        if (Test-Path $outputPath) {
            $inputSize = (Get-Item $binaryPath).Length
            $outputSize = (Get-Item $outputPath).Length
            Write-Host "  Input file size:  $inputSize bytes" -ForegroundColor Gray
            Write-Host "  Output file size: $outputSize bytes" -ForegroundColor Gray
        }
    } else {
        $errorMsg = $converter.GetLastError()
        Write-Host "✗ Conversion failed!" -ForegroundColor Red
        Write-Host "  Error: $errorMsg" -ForegroundColor Red
    }
    
    # Release COM object
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($converter) | Out-Null
    
} catch {
    Write-Host "✗ Error: Failed to create COM object" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure the COM class is registered. Run register_com.bat as Administrator." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Test Complete" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
