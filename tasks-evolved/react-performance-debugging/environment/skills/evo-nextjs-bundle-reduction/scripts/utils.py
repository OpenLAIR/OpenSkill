import re
import os

def fix_barrel_lodash_imports(filepath):
    """Replace barrel lodash imports with individual module imports."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Match: import { func1, func2, ... } from 'lodash';
    pattern = r"import\s*\{([^}]+)\}\s*from\s*['\"]lodash['\"];?"
    match = re.search(pattern, content)
    if not match:
        return False
    
    funcs_str = match.group(1)
    funcs = [f.strip() for f in funcs_str.split(',') if f.strip()]
    
    # Build individual imports
    individual_imports = []
    for func in funcs:
        individual_imports.append(f"import {func} from 'lodash/{func}';")
    
    replacement = '\n'.join(individual_imports)
    content = content[:match.start()] + replacement + content[match.end():]
    
    with open(filepath, 'w') as f:
        f.write(content)
    return True

def extract_and_dynamify_component(source_filepath, component_name, target_dir='/app/src/components'):
    """Extract a component from a file into its own file and replace with dynamic import."""
    with open(source_filepath, 'r') as f:
        content = f.read()
    
    # Find the component function and its body
    # Pattern: function ComponentName({ ... }) { ... }
    # We need to find the full function including nested braces
    func_start = content.find(f'function {component_name}(')
    if func_start == -1:
        return False
    
    # Find the opening brace of the function body
    brace_pos = content.find('{', content.find(')', func_start))
    if brace_pos == -1:
        return False
    
    # Count braces to find the end
    depth = 0
    end_pos = brace_pos
    for i in range(brace_pos, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    
    component_body = content[func_start:end_pos]
    
    # Extract the component to a new file
    # Need to include necessary imports (mathjs, lodash individual)
    # Check what the component uses
    needs_mathjs = 'mathjs' in component_body or any(x in component_body for x in ['mean(', 'std(', 'median(', 'quantileSeq(', 'variance('])
    needs_lodash_sortby = 'sortBy(' in component_body
    
    new_file_content = "'use client';\n\n"
    
    if needs_lodash_sortby:
        new_file_content += "import sortBy from 'lodash/sortBy';\n"
    if needs_mathjs:
        new_file_content += "import { mean, std, median, quantileSeq, variance } from 'mathjs';\n"
    
    new_file_content += "\n"
    
    # Add Product interface
    new_file_content += """interface Product {
  id: string;
  name: string;
  price: number;
  category: string;
  rating: number;
  reviews: number;
  inStock: boolean;
}

"""
    
    # Add export to the component
    new_file_content += f"export default {component_body}\n"
    
    # Write the new component file
    target_path = os.path.join(target_dir, f'{component_name}.tsx')
    with open(target_path, 'w') as f:
        f.write(new_file_content)
    
    # Remove the component from the source file
    content = content[:func_start] + content[end_pos:]
    
    # Remove the mathjs import from source if only used by extracted component
    content = re.sub(r"import\s*\{[^}]*\}\s*from\s*['\"]mathjs['\"];?\n?", '', content)
    
    # Add dynamic import at the top (after existing imports)
    # Find the last import line
    import_lines = []
    non_import_start = 0
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('import ') or stripped.startswith("'use client'") or stripped == '':
            non_import_start += len(line) + 1
        else:
            break
    
    # Check if dynamic is already imported
    if "import dynamic from 'next/dynamic'" not in content:
        dynamic_import = "import dynamic from 'next/dynamic';\n"
    else:
        dynamic_import = ''
    
    dynamic_component = f"\nconst {component_name} = dynamic(() => import('@/components/{component_name}'), {{\n  ssr: false,\n  loading: () => <div data-testid=\"advanced-content\">Loading...</div>\n}});\n"
    
    # Insert after imports
    content = content[:non_import_start] + dynamic_import + dynamic_component + content[non_import_start:]
    
    with open(source_filepath, 'w') as f:
        f.write(content)
    
    return True

def apply_bundle_fixes(compare_page_path):
    """Apply all bundle optimization fixes."""
    fix_barrel_lodash_imports(compare_page_path)
    extract_and_dynamify_component(compare_page_path, 'AdvancedAnalysis')
    return True
