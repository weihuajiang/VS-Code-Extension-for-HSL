using HxSecurityComLib;
using System;

namespace AddCheckSum
{
    internal class Program
    {
        static int Main(string[] args)
        {
            if (args.Length < 1)
            {
                Console.Error.WriteLine("Usage: AddCheckSum.exe <filename>");
                return 1;
            }

            var security = new HxSecurityCom() as IHxSecurityFileCom2;
            if (security == null)
            {
                Console.Error.WriteLine(
                    "Failed to obtain IHxSecurityFileCom2 interface. " +
                    "Ensure Hamilton.HxSecurityCom is registered as a 32-bit COM object " +
                    "(regsvr32 on the native DLL, or regasm /codebase with 32-bit .NET Framework regasm).");
                return 2;
            }

            security.SetFileValidation(args[0], 0, "//");
            return 0;
        }
    }
}
