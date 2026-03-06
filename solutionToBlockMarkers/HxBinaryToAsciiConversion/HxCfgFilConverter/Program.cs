using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace HxCfgFilConverter;

internal static class Program
{
	[STAThread]
	private static void Main(string[] args)
	{
		if (args.Length != 0)
		{
			if (!AttachConsole(-1))
			{
				AllocConsole();
			}
			ProcessCommandLine(args);
			FreeConsole();
		}
		else
		{
			Application.EnableVisualStyles();
			Application.SetCompatibleTextRenderingDefault(defaultValue: false);
			Application.Run(new Form1());
		}
	}

	private static void ProcessCommandLine(string[] args)
	{
		if (args.Length != 2)
		{
			PrintUsage();
			return;
		}
		if (args[0] == "/b")
		{
			Console.WriteLine("converting " + args[1] + " to binary.");
			try
			{
				Converter converter = new Converter();
				converter.LoadFile(args[1]);
				converter.SerializeFile(args[1]);
				Console.WriteLine("Conversion completed successfully");
				return;
			}
			catch (Exception ex)
			{
				Console.WriteLine("Exception occured: " + ex.Message);
				return;
			}
		}
		if (args[0] == "/t")
		{
			Console.WriteLine("converting " + args[1] + " to ascii.");
			try
			{
				Converter converter2 = new Converter();
				converter2.LoadFile(args[1]);
				converter2.StoreFile(args[1]);
				Console.WriteLine("Conversion completed successfully");
				return;
			}
			catch (Exception ex2)
			{
				Console.WriteLine("Exception occured: " + ex2.Message);
				return;
			}
		}
		PrintUsage();
	}

	private static void PrintUsage()
	{
		Console.WriteLine("Usage: HxCfgFilConverter [Option] Filename");
		Console.WriteLine("Options: \n'/b': Converts the file specified to binary form.");
		Console.WriteLine("'/t': Converts the file specified to text form.");
	}

	[DllImport("kernel32.dll")]
	private static extern bool AllocConsole();

	[DllImport("kernel32.dll")]
	private static extern bool AttachConsole(int pid);

	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern bool FreeConsole();
}
