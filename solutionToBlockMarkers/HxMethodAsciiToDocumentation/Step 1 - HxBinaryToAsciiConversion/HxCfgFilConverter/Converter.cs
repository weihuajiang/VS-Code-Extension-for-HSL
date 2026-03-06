using System;
using System.Runtime.InteropServices;
using Hamilton.Interop.HxCfgFil;

namespace HxCfgFilConverter;

internal class Converter
{
	private short status = -1;

	private HxCfgFile hxCfgFile;

	public void LoadFile(string filename)
	{
		hxCfgFile = (HxCfgFile)Activator.CreateInstance(Marshal.GetTypeFromCLSID(new Guid("F4B19511-207B-11D1-8C7D-004095E12BC7")));
		status = hxCfgFile.LoadFile(filename);
	}

	public void StoreFile(string filename)
	{
		hxCfgFile.StoreFile(filename, status);
	}

	public void SerializeFile(string filename)
	{
		hxCfgFile.SerializeFile(filename, status);
	}
}
