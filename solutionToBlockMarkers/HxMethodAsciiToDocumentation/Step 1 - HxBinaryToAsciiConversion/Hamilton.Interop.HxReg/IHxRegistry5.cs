using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Hamilton.Interop.HxReg;

[ComImport]
[CompilerGenerated]
[Guid("3CBA017E-C8F3-44C9-826C-9C56F654EA28")]
[TypeIdentifier]
public interface IHxRegistry5 : IHxRegistry4
{
	[DispId(1)]
	string BinPath
	{
		[MethodImpl(MethodImplOptions.InternalCall, MethodCodeType = MethodCodeType.Runtime)]
		[DispId(1)]
		[return: MarshalAs(UnmanagedType.BStr)]
		get;
	}
}
