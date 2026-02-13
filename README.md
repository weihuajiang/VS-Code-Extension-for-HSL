# HSL (Hamilton) Language Support

A VS Code extension providing comprehensive syntax highlighting, code snippets, and language support for **HSL (Hamilton Standard Language)**.

> 📖 **Learning Resources**: Check out the [How to create a VS Code Extension (for HSL)](https://pig.abbvienet.com/orgs/VENUS-Library-Development/discussions/3) guide for detailed information on extension development.

## Features

- ✅ **Syntax Highlighting**: Full HSL syntax highlighting with support for keywords, data types, operators, and comments
- ✅ **Code Snippets**: Pre-built templates for common HSL patterns:
  - Function declarations
  - Method definitions
  - Namespace blocks
  - Error handling with `err.Raise`
  - Trace output
- ✅ **Bracket Matching & Auto-closing**: Automatic bracket pairing for `{}`, `[]`, `()`, and quotes
- ✅ **Code Folding**: Support for region-based code folding using `// #region` and `// #endregion` markers
- ✅ **Language Configuration**: Proper handling of HSL comments, keywords, and operators

## Supported File Extensions

This extension supports the following HSL file formats:
- `.hsl` - Standard HSL source files
- `.hs_` - HSL variant files
- `.stp` - Hamilton step files

## Language Support

### Keywords
- Control flow: `if`, `else`, `for`, `while`, `do`, `switch`, `case`, `default`, `break`, `continue`, `return`
- Exception handling: `throw`, `try`, `catch`
- HSL-specific: `activity`, `actionblock`, `executoronly`, `oncancelaction`, `oncanceltask`, `resource`, `reschedule`, `schedule`, `scheduleronly`, `schedulerprompt`, `workflow`
- Declarations: `namespace`, `function`, `method`, `dialog`, `class`
- Modifiers: `private`, `public`, `protected`, `static`, `const`
- Debug: `debug`, `echo`

### Supported Data Types
- Primitives: `integer`, `int`, `real`, `double`, `float`, `string`, `bool`, `boolean`
- Complex: `variable`, `object`, `void`
- Constants: `hslTrue`, `hslFalse`, `true`, `false`

### Built-in Functions
- `Trace()` - Output trace information
- `GetFunctionName()` - Get current function name
- `Sleep()` - Pause execution
- `Wait()` - Wait for condition
- `MessageBox()` - Display message dialog
- `err.Raise()` - Raise error with message

## Quick Start

1. **Install** the extension from the VS Code Marketplace
2. **Open** or create a file with `.hsl`, `.hs_`, or `.stp` extension
3. **Use snippets** by typing:
   - `hslfunc` - Function template
   - `hslmethod` - Method template
   - `hslns` - Namespace block
   - `raise` - Error raising statement
   - `trace` - Trace output

For more detailed guidance on developing and extending this extension, visit the [How to create a VS Code Extension (for HSL)](https://pig.abbvienet.com/orgs/VENUS-Library-Development/discussions/3) documentation.

## Requirements

- VS Code 1.85.0 or later

## Known Issues

None at this time. Please report any issues on the extension's repository.

## Release Notes

### 1.0.1

Initial release of HSL Language Support featuring:
- Full syntax highlighting for Hamilton Standard Language
- Code snippet templates for common patterns
- Bracket matching and auto-closing pairs
- Code folding support
- Comprehensive language configuration

## Additional Resources

- **[How to create a VS Code Extension (for HSL)](https://pig.abbvienet.com/orgs/VENUS-Library-Development/discussions/3)** - Comprehensive guide for HSL extension development and best practices
- [VS Code Extension API Documentation](https://code.visualstudio.com/api)
- [TextMate Grammar Documentation](https://macromates.com/manual/en/language_grammars)

