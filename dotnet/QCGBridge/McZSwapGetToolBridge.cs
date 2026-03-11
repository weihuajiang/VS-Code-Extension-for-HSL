using System;
using System.Runtime.InteropServices;

namespace QCGBridge
{
    // -----------------------------------------------------------------------
    // IInstrumentCommands -- partial definition for the methods we need.
    // Full interface GUID: {B2144486-AB9B-11D2-8D4F-0004ACB05FD4}
    // Implemented by HxAtsInstrumentClass (native HxAtsInstrument.dll).
    //
    // Only the methods we call are declared here; order and DISPIDs must
    // match the real type library exactly for IDispatch::Invoke to work.
    // -----------------------------------------------------------------------
    [ComImport]
    [Guid("B2144486-AB9B-11D2-8D4F-0004ACB05FD4")]
    [InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
    internal interface IInstrumentCommands
    {
        [DispId(55)]
        int McGetInstrumentState([MarshalAs(UnmanagedType.Struct)] object pinParameter);

        [DispId(98)]
        int McZSwapGetTool([MarshalAs(UnmanagedType.Struct)] object pinParameter);

        [DispId(99)]
        int McZSwapEjectTool([MarshalAs(UnmanagedType.Struct)] object pinParameter);
    }

    // -----------------------------------------------------------------------
    // COM-visible bridge class.
    //
    // HSL usage:
    //   private object bridge;
    //   bridge.CreateObject("QCGBridge.McZSwapBridge", hslFalse);
    //   bridge.CallMcZSwapGetTool(cmdObj, parsIn);
    //   bridge.ReleaseObject();
    //
    // The bridge tries three approaches to reach McZSwapGetTool:
    //   1. QueryInterface the cmdObj for IInstrumentCommands (works if
    //      HxAtsInstrument aggregates HxGruCommand via COM aggregation).
    //   2. Marshal.GetActiveObject("Hamilton.HxAtsInstrument") -- finds the
    //      running instance via the COM Running Object Table.
    //   3. Late-bound IDispatch call of "McZSwapGetTool" on the cmdObj
    //      (works if HxGruCommand forwards unknown DISPIDs to its parent).
    //
    // At least one of these should succeed. Diagnostic output is written
    // to the system trace via System.Diagnostics.Trace so it appears in
    // the Hamilton .trc log file.
    // -----------------------------------------------------------------------
    [ComVisible(true)]
    [Guid("D1E2F3A4-5B6C-7D8E-9F0A-1B2C3D4E5F6A")]
    [ProgId("QCGBridge.McZSwapBridge")]
    [ClassInterface(ClassInterfaceType.AutoDispatch)]
    public class McZSwapBridge
    {
        // -------------------------------------------------------------------
        // CallMcZSwapGetTool
        //
        // Attempts to call McZSwapGetTool (DISPID 98) on the HxAtsInstrument
        // COM object.
        //
        // Parameters:
        //   commandObj -- the result of ML_STAR.GetCommandObject() in HSL
        //                 (IHxGruCommandRun7 on HxGruCommand)
        //   parsIn     -- HxPars COM object with ZSwapGetTool parameters
        //
        // Returns:
        //   0 on success, non-zero HRESULT on failure
        // -------------------------------------------------------------------
        public int CallMcZSwapGetTool(object commandObj, object parsIn)
        {
            if (commandObj == null)
                return unchecked((int)0x80004003); // E_POINTER

            // --- Approach 1: QueryInterface for IInstrumentCommands ---
            // If HxAtsInstrument aggregates HxGruCommand, QI on the inner
            // object delegates to the outer and returns the interface.
            try
            {
                Log("QCGBridge: Approach 1 -- QueryInterface for IInstrumentCommands on cmdObj...");
                var instrument = (IInstrumentCommands)commandObj;
                Log("QCGBridge: QI succeeded! Calling McZSwapGetTool...");
                int hr = instrument.McZSwapGetTool(parsIn);
                Log("QCGBridge: McZSwapGetTool returned " + hr);
                return hr;
            }
            catch (InvalidCastException)
            {
                Log("QCGBridge: Approach 1 failed -- cmdObj does not support IInstrumentCommands (no COM aggregation).");
            }
            catch (Exception ex)
            {
                Log("QCGBridge: Approach 1 exception: " + ex.GetType().Name + " -- " + ex.Message);
            }

            // --- Approach 2: GetActiveObject from ROT ---
            try
            {
                Log("QCGBridge: Approach 2 -- Marshal.GetActiveObject(\"Hamilton.HxAtsInstrument\")...");
                object atsObj = Marshal.GetActiveObject("Hamilton.HxAtsInstrument");
                var instrument = (IInstrumentCommands)atsObj;
                Log("QCGBridge: GetActiveObject succeeded! Calling McZSwapGetTool...");
                int hr = instrument.McZSwapGetTool(parsIn);
                Log("QCGBridge: McZSwapGetTool returned " + hr);
                return hr;
            }
            catch (COMException comEx)
            {
                Log("QCGBridge: Approach 2 failed -- " + comEx.Message + " (HR=0x" + comEx.ErrorCode.ToString("X8") + ")");
            }
            catch (Exception ex)
            {
                Log("QCGBridge: Approach 2 exception: " + ex.GetType().Name + " -- " + ex.Message);
            }

            // --- Approach 3: Late-bound IDispatch call ---
            // Try calling McZSwapGetTool as a late-bound dispatch method
            // on the commandObj.  If HxGruCommand's IDispatch implementation
            // forwards unknown names to HxAtsInstrument, this works.
            try
            {
                Log("QCGBridge: Approach 3 -- Late-bound IDispatch call on cmdObj...");
                Type dispType = commandObj.GetType();
                object result = dispType.InvokeMember(
                    "McZSwapGetTool",
                    System.Reflection.BindingFlags.InvokeMethod,
                    null,
                    commandObj,
                    new object[] { parsIn });
                int hr = Convert.ToInt32(result);
                Log("QCGBridge: Late-bound call returned " + hr);
                return hr;
            }
            catch (Exception ex)
            {
                Log("QCGBridge: Approach 3 failed -- " + ex.GetType().Name + " -- " + ex.Message);
            }

            Log("QCGBridge: All approaches failed. McZSwapGetTool is not accessible from the provided command object.");
            return unchecked((int)0x80004002); // E_NOINTERFACE
        }

        // -------------------------------------------------------------------
        // CallMcGetInstrumentState
        //
        // Calls McGetInstrumentState (DISPID 55) to read current state.
        // Uses the same three-approach pattern.
        // -------------------------------------------------------------------
        public int CallMcGetInstrumentState(object commandObj, object parsIn)
        {
            if (commandObj == null)
                return unchecked((int)0x80004003);

            // Approach 1: QI
            try
            {
                var instrument = (IInstrumentCommands)commandObj;
                return instrument.McGetInstrumentState(parsIn);
            }
            catch (InvalidCastException) { }
            catch (Exception) { }

            // Approach 2: ROT
            try
            {
                object atsObj = Marshal.GetActiveObject("Hamilton.HxAtsInstrument");
                var instrument = (IInstrumentCommands)atsObj;
                return instrument.McGetInstrumentState(parsIn);
            }
            catch (Exception) { }

            // Approach 3: Late-bound
            try
            {
                Type dispType = commandObj.GetType();
                object result = dispType.InvokeMember(
                    "McGetInstrumentState",
                    System.Reflection.BindingFlags.InvokeMethod,
                    null,
                    commandObj,
                    new object[] { parsIn });
                return Convert.ToInt32(result);
            }
            catch (Exception) { }

            return unchecked((int)0x80004002);
        }

        // -------------------------------------------------------------------
        // GetDiagnosticInfo
        //
        // Returns a diagnostic string with COM object identity information.
        // Useful for troubleshooting which interfaces the cmdObj supports.
        // -------------------------------------------------------------------
        public string GetDiagnosticInfo(object commandObj)
        {
            if (commandObj == null)
                return "commandObj is null";

            var sb = new System.Text.StringBuilder();
            sb.AppendLine("QCGBridge Diagnostic Info");
            sb.AppendLine("========================");

            // Object type
            Type t = commandObj.GetType();
            sb.AppendLine("CLR Type: " + t.FullName);
            sb.AppendLine("COM Type: " + (t.IsCOMObject ? "Yes" : "No"));
            sb.AppendLine("GUID: " + t.GUID);

            // Check known interfaces
            Guid iidInstrumentCommands = new Guid("B2144486-AB9B-11D2-8D4F-0004ACB05FD4");
            Guid iidInstrumentCommandsVantage = new Guid("069C0D2B-477B-4CED-AAE4-598CE14A1F89");
            Guid iidHxGruCommandRun7 = new Guid("ED5B0123-1FED-11d4-BE1F-08005AD316DE"); // TypeLib GUID

            IntPtr pUnk = Marshal.GetIUnknownForObject(commandObj);
            try
            {
                IntPtr pIface;
                int hr;

                hr = Marshal.QueryInterface(pUnk, ref iidInstrumentCommands, out pIface);
                sb.AppendLine("QI IInstrumentCommands: " + (hr == 0 ? "YES" : "No (0x" + hr.ToString("X8") + ")"));
                if (hr == 0) Marshal.Release(pIface);

                hr = Marshal.QueryInterface(pUnk, ref iidInstrumentCommandsVantage, out pIface);
                sb.AppendLine("QI IInstrumentCommandsVantage: " + (hr == 0 ? "YES" : "No (0x" + hr.ToString("X8") + ")"));
                if (hr == 0) Marshal.Release(pIface);
            }
            finally
            {
                Marshal.Release(pUnk);
            }

            // Check ROT
            try
            {
                object atsObj = Marshal.GetActiveObject("Hamilton.HxAtsInstrument");
                sb.AppendLine("ROT GetActiveObject: Found HxAtsInstrument");
                Marshal.ReleaseComObject(atsObj);
            }
            catch (COMException ex)
            {
                sb.AppendLine("ROT GetActiveObject: Not found (0x" + ex.ErrorCode.ToString("X8") + ")");
            }

            return sb.ToString();
        }

        private static void Log(string message)
        {
            System.Diagnostics.Trace.WriteLine(message);
        }
    }
}
