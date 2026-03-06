using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Hamilton.Interop.HxCfgFil;

[ComImport]
[CompilerGenerated]
[Guid("8FFC9B23-8377-47C2-BA48-7473BF9D9824")]
[TypeIdentifier]
public interface IHxCfgFile6 : IHxCfgFile5
{
	void _VtblGap1_2();

	[MethodImpl(MethodImplOptions.InternalCall, MethodCodeType = MethodCodeType.Runtime)]
	[DispId(3)]
	short LoadFile([In][MarshalAs(UnmanagedType.BStr)] string iFileSpec);

	[MethodImpl(MethodImplOptions.InternalCall, MethodCodeType = MethodCodeType.Runtime)]
	[DispId(4)]
	void StoreFile([In][MarshalAs(UnmanagedType.BStr)] string iFileSpec, [In] short iCfgStatus);

	void _VtblGap2_13();

	[MethodImpl(MethodImplOptions.InternalCall, MethodCodeType = MethodCodeType.Runtime)]
	[DispId(18)]
	void SerializeFile([In][MarshalAs(UnmanagedType.BStr)] string iFileSpec, [In] short iCfgStatus);
}
