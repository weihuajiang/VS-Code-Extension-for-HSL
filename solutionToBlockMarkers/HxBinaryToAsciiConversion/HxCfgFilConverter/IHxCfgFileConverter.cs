using System;
using System.Runtime.InteropServices;

namespace HxCfgFilConverter;

/// <summary>
/// COM interface for converting Hamilton config files from binary to ASCII
/// </summary>
[ComVisible(true)]
[Guid("A1B2C3D4-5E6F-7890-ABCD-EF1234567890")]
[InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
public interface IHxCfgFileConverter
{
	/// <summary>
	/// Converts a binary config file to ASCII format
	/// </summary>
	/// <param name="binaryFilePath">Full path to the source binary file</param>
	/// <param name="asciiFilePath">Full path where the ASCII file should be saved</param>
	/// <returns>True if conversion was successful, false otherwise</returns>
	[DispId(1)]
	bool ConvertBinaryToAscii(string binaryFilePath, string asciiFilePath);

	/// <summary>
	/// Gets the last error message if conversion failed
	/// </summary>
	/// <returns>Error message or empty string if no error</returns>
	[DispId(2)]
	string GetLastError();
}
