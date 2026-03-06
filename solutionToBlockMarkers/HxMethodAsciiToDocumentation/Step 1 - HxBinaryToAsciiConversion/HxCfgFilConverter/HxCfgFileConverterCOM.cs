using System;
using System.IO;
using System.Runtime.InteropServices;

namespace HxCfgFilConverter;

/// <summary>
/// COM class for converting Hamilton config files from binary to ASCII
/// </summary>
[ComVisible(true)]
[Guid("B2C3D4E5-6F70-8091-BCDE-F12345678901")]
[ClassInterface(ClassInterfaceType.None)]
[ProgId("HxCfgFilConverter.HxCfgFileConverterCOM")]
public class HxCfgFileConverterCOM : IHxCfgFileConverter
{
	private string lastError = string.Empty;

	/// <summary>
	/// Converts a binary config file to ASCII format
	/// </summary>
	/// <param name="binaryFilePath">Full path to the source binary file</param>
	/// <param name="asciiFilePath">Full path where the ASCII file should be saved</param>
	/// <returns>True if conversion was successful, false otherwise</returns>
	public bool ConvertBinaryToAscii(string binaryFilePath, string asciiFilePath)
	{
		lastError = string.Empty;

		try
		{
			// Validate input parameters
			if (string.IsNullOrWhiteSpace(binaryFilePath))
			{
				lastError = "Binary file path cannot be empty";
				return false;
			}

			if (string.IsNullOrWhiteSpace(asciiFilePath))
			{
				lastError = "ASCII file path cannot be empty";
				return false;
			}

			// Check if source file exists
			if (!File.Exists(binaryFilePath))
			{
				lastError = $"Source file not found: {binaryFilePath}";
				return false;
			}

			// Ensure output directory exists
			string outputDirectory = Path.GetDirectoryName(asciiFilePath);
			if (!string.IsNullOrEmpty(outputDirectory) && !Directory.Exists(outputDirectory))
			{
				try
				{
					Directory.CreateDirectory(outputDirectory);
				}
				catch (Exception ex)
				{
					lastError = $"Failed to create output directory: {ex.Message}";
					return false;
				}
			}

			// Create a temporary copy of the binary file
			string tempFile = Path.GetTempFileName();
			try
			{
				File.Copy(binaryFilePath, tempFile, true);

				// Load and convert the temporary file
				Converter converter = new Converter();
				converter.LoadFile(tempFile);
				converter.StoreFile(tempFile);

				// Move the converted file to the destination
				File.Copy(tempFile, asciiFilePath, true);

				return true;
			}
			finally
			{
				// Clean up temporary file
				if (File.Exists(tempFile))
				{
					try
					{
						File.Delete(tempFile);
					}
					catch
					{
						// Ignore cleanup errors
					}
				}
			}
		}
		catch (Exception ex)
		{
			lastError = $"Conversion failed: {ex.Message}";
			return false;
		}
	}

	/// <summary>
	/// Gets the last error message if conversion failed
	/// </summary>
	/// <returns>Error message or empty string if no error</returns>
	public string GetLastError()
	{
		return lastError;
	}

	/// <summary>
	/// COM registration function
	/// </summary>
	[ComRegisterFunction]
	public static void RegisterFunction(Type type)
	{
		// Optional: Add custom registration steps here if needed
	}

	/// <summary>
	/// COM unregistration function
	/// </summary>
	[ComUnregisterFunction]
	public static void UnregisterFunction(Type type)
	{
		// Optional: Add custom unregistration steps here if needed
	}
}
