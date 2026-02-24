using HxSecurityComLib;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace AddCheckSum
{
    internal class Program
    {
        static void Main(string[] args)
        {
            var security = new HxSecurityCom() as IHxSecurityFileCom2;
            security.SetFileValidation(args[0], 0, "//");
        }
    }
}
