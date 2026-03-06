import csv
import re

def clean_description(desc):
    """Clean up description text by removing special characters and formatting."""
    if not desc:
        return ""
    # Remove \r\n and replace with spaces
    desc = desc.replace('\\r\\n', ' ')
    # Remove special hex characters like \0xb5 and \0x93
    desc = re.sub(r'\\0x[0-9a-fA-F]{2}', '', desc)
    # Clean up multiple spaces
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()

def parse_submethods(file_path):
    """Parse the AntibodyScreening.txt file and extract all submethods."""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip().strip(',').strip('"') for line in f]
    
    submethods = []
    i = 0
    
    while i < len(lines):
        # Look for parameter section marker (-533725169)
        # This marks the start of a method's parameter list
        if lines[i] == '(-533725169':
            method_data = {
                'name': '',
                'description': '',
                'variables': []
            }
            
            # Parse all variables in this parameters section
            i += 1
            paren_depth = 0
            
            while i < len(lines):
                line = lines[i]
                
                # Track when we enter/exit parameter blocks
                if re.match(r'^\(\d+$', line):
                    # Start of a parameter block like "(0", "(1", "(2"
                    var_description = ''
                    var_name = ''
                    paren_depth += 1
                    
                    # Scan through this parameter block
                    j = i + 1
                    while j < len(lines):
                        if lines[j] == ')':
                            # End of this parameter block
                            break
                        elif lines[j] == '1-533725167':
                            # Next line contains variable description
                            if j + 1 < len(lines):
                                var_description = lines[j + 1]
                                j += 1
                        elif lines[j] == '1-533725168':
                            # Next line contains variable name
                            if j + 1 < len(lines):
                                var_name = lines[j + 1]
                                j += 1
                        j += 1
                    
                    # Add variable if we found a name
                    if var_name:
                        method_data['variables'].append({
                            'name': var_name,
                            'description': var_description
                        })
                    
                    # Move past this parameter block
                    i = j
                
                elif line == ')':
                    # Check if this closes the entire parameters section
                    # by looking ahead for description and method name markers
                    if i + 1 < len(lines) and lines[i + 1] == '1-533725170':
                        # This closes the parameters section
                        # Now get description and method name
                        i += 1  # Move to 1-533725170
                        if i + 1 < len(lines):
                            method_data['description'] = clean_description(lines[i + 1])
                            i += 1  # Move to description text
                        
                        # Look for method name ahead
                        while i < len(lines):
                            if lines[i] == '1-533725161':
                                if i + 1 < len(lines):
                                    method_data['name'] = lines[i + 1]
                                break
                            i += 1
                        
                        # Add method to list
                        if method_data['name']:
                            submethods.append(method_data)
                        break
                
                i += 1
        else:
            i += 1
    
    return submethods

def write_to_csv(submethods, output_path):
    """Write submethods to a CSV file."""
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(['Method Name', 'Description', 'Variable Name', 'Variable Description'])
        
        # Write data
        for method in submethods:
            if method['variables']:
                # Write first variable with method name and description
                first_var = method['variables'][0]
                writer.writerow([
                    method['name'],
                    method['description'],
                    first_var['name'],
                    first_var['description']
                ])
                
                # Write remaining variables (blank method name and description)
                for var in method['variables'][1:]:
                    writer.writerow([
                        '',
                        '',
                        var['name'],
                        var['description']
                    ])
            else:
                # Method with no variables
                writer.writerow([
                    method['name'],
                    method['description'],
                    '',
                    ''
                ])

def main():
    input_file = r'c:\Users\admin\Desktop\AntibodyScreening.txt'
    output_file = r'c:\Users\admin\Desktop\submethods_extracted.csv'
    
    print(f"Parsing {input_file}...")
    submethods = parse_submethods(input_file)
    
    print(f"\nFound {len(submethods)} submethods:")
    for method in submethods:
        var_count = len(method['variables'])
        print(f"  • {method['name']}: {var_count} variable(s)")
    
    print(f"\nWriting to {output_file}...")
    write_to_csv(submethods, output_file)
    
    print("\n✓ Done! CSV file created successfully.")

if __name__ == '__main__':
    main()
